from __future__ import annotations

import argparse
import json
import os
import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

import httpx
from openai import BadRequestError, OpenAI


DEFAULT_APP_URL = "http://127.0.0.1:8000"
DEFAULT_OPENAI_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-20b"


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_tags(html_fragment: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", html_fragment, flags=re.S)
    return " ".join(unescape(cleaned).split())


def _extract_json_object(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


@dataclass
class RunnerConfig:
    app_url: str
    output_path: Path
    logs_path: Path
    sessions: int
    turns_per_session: int
    preset_name: str
    pack_id: int | None
    delay_ms: int
    timeout_seconds: float
    openai_base_url: str
    openai_model: str
    openai_api_key: str | None
    seed: int
    dry_run: bool
    verbose: bool

    @classmethod
    def from_args(cls) -> "RunnerConfig":
        parser = argparse.ArgumentParser(
            description=(
                "Generate synthetic cards-flow dataset by simulating a B2 learner with "
                "persistent mistake patterns. Uses OpenAI-compatible chat API."
            )
        )
        parser.add_argument("--app-url", default=os.getenv("APP_BASE_URL", DEFAULT_APP_URL))
        parser.add_argument(
            "--output",
            default="data/synthetic_cards_dataset.jsonl",
            help="Output JSONL dataset path.",
        )
        parser.add_argument(
            "--logs-path",
            default="logs/logs.jsonl",
            help="App logs JSONL path for sid-linked event aggregation.",
        )
        parser.add_argument("--sessions", type=int, default=2)
        parser.add_argument("--turns", type=int, default=30, dest="turns_per_session")
        parser.add_argument("--preset-name", default="Default")
        parser.add_argument("--pack-id", type=int, default=None)
        parser.add_argument("--delay-ms", type=int, default=150)
        parser.add_argument("--timeout-seconds", type=float, default=30.0)
        parser.add_argument(
            "--openai-base-url",
            default=os.getenv("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL),
        )
        parser.add_argument(
            "--model",
            default=os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
            dest="openai_model",
        )
        parser.add_argument("--seed", type=int, default=11)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--verbose", action="store_true")
        args = parser.parse_args()

        openai_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
        if not args.dry_run and not openai_api_key:
            raise RuntimeError("Set OPENAI_API_KEY (or GROQ_API_KEY) to run without --dry-run.")

        return cls(
            app_url=args.app_url.rstrip("/"),
            output_path=Path(args.output),
            logs_path=Path(args.logs_path),
            sessions=max(1, args.sessions),
            turns_per_session=max(1, args.turns_per_session),
            preset_name=args.preset_name,
            pack_id=args.pack_id,
            delay_ms=max(0, args.delay_ms),
            timeout_seconds=max(1.0, args.timeout_seconds),
            openai_base_url=args.openai_base_url.rstrip("/"),
            openai_model=args.openai_model,
            openai_api_key=openai_api_key,
            seed=args.seed,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )


class OpenAICompatClient:
    def __init__(self, cfg: RunnerConfig) -> None:
        self.cfg = cfg
        self._client: OpenAI | None = None
        if not cfg.dry_run and not cfg.openai_api_key:
            raise RuntimeError("OpenAI-compatible API key is required unless --dry-run is enabled.")
        if not cfg.dry_run:
            self._client = OpenAI(
                api_key=cfg.openai_api_key,
                base_url=cfg.openai_base_url,
                timeout=cfg.timeout_seconds,
            )

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    @staticmethod
    def _content_to_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            fragments: list[str] = []
            for part in content:
                if isinstance(part, dict):
                    txt = part.get("text")
                    if isinstance(txt, str):
                        fragments.append(txt)
                elif hasattr(part, "text") and isinstance(part.text, str):
                    fragments.append(part.text)
            if fragments:
                return "\n".join(fragments)
        raise ValueError("Expected text content in model response.")

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if self.cfg.dry_run:
            return {"mode": "dry_run", "confidence": 0.5}
        if self._client is None:
            raise RuntimeError("OpenAI client is not initialized.")

        kwargs: dict[str, Any] = {
            "model": self.cfg.openai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        try:
            completion = self._client.chat.completions.create(**kwargs)
            parsed = _extract_json_object(self._content_to_text(completion.choices[0].message.content))
            if parsed is None:
                raise ValueError("Model response was not valid JSON object.")
            return parsed
        except BadRequestError:
            # Some OpenAI-compatible endpoints reject response_format.
            pass

        kwargs.pop("response_format", None)
        completion = self._client.chat.completions.create(**kwargs)
        parsed = _extract_json_object(self._content_to_text(completion.choices[0].message.content))
        if parsed is None:
            raise ValueError("Model response was not valid JSON object.")
        return parsed


@dataclass
class LearnerProfile:
    learner_id: str
    error_style: str
    base_error_rate: float
    confidence_shift: float
    wrong_option_offset: int
    action_under_rate: float
    randomizer: random.Random = field(repr=False)

    def should_make_mistake(self, turn: int, task_type: str) -> bool:
        task_shift = {"flashcard": -0.05, "fill_gap": 0.05, "which_definition": 0.1}.get(task_type, 0.0)
        fatigue = min(0.2, turn * 0.006)
        chance = _clamp(self.base_error_rate + task_shift + fatigue, 0.05, 0.9)
        return self.randomizer.random() < chance


def build_profile(session_seed: int) -> LearnerProfile:
    rnd = random.Random(session_seed)
    style = rnd.choice(["missing_vowel", "double_letter", "neighbor_choice"])
    return LearnerProfile(
        learner_id=f"b2-sim-{session_seed}",
        error_style=style,
        base_error_rate=rnd.uniform(0.22, 0.38),
        confidence_shift=rnd.uniform(-0.12, 0.08),
        wrong_option_offset=rnd.choice([1, 2]),
        action_under_rate=rnd.uniform(0.15, 0.4),
        randomizer=rnd,
    )


@dataclass
class DefinitionOption:
    word_id: int
    definition: str


@dataclass
class CardState:
    task_type: str
    word: str | None
    gap_text: str | None
    fill_choices: list[str]
    definition_options: list[DefinitionOption]
    action_buttons: list[str]
    definitions: list[str]


def parse_card_state(html: str) -> CardState:
    is_fill_gap = 'task-label muted">Fill in the gap' in html
    is_which_definition = 'task-label muted">Which definition fits?' in html
    task_type = "flashcard"
    if is_fill_gap:
        task_type = "fill_gap"
    elif is_which_definition:
        task_type = "which_definition"

    word: str | None = None
    if is_which_definition:
        match = re.search(
            r'Which definition fits\?</div>\s*<div class="word"[^>]*>(.*?)</div>',
            html,
            flags=re.S,
        )
        if match:
            word = _strip_tags(match.group(1))
    else:
        match = re.search(r'<div class="word">(.*?)</div>', html, flags=re.S)
        if match:
            candidate = _strip_tags(match.group(1))
            word = candidate if candidate != "\u2014" else None

    gap_text: str | None = None
    if is_fill_gap:
        match = re.search(r'<div class="gap-text">(.*?)</div>', html, flags=re.S)
        if match:
            gap_text = _strip_tags(match.group(1))

    fill_choices: list[str] = []
    for match in re.finditer(
        r'<button[^>]*class="[^"]*task-choice[^"]*"[^>]*onclick="submitTask\(\'([^\']*)\'\)"[^>]*>(.*?)</button>',
        html,
        flags=re.S,
    ):
        submitted, rendered = match.groups()
        fill_choices.append(_strip_tags(submitted or rendered))

    definition_options: list[DefinitionOption] = []
    for match in re.finditer(
        r'<button[^>]*class="[^"]*def-option[^"]*"[^>]*onclick="submitTask\(\'(\d+)\'\)"[^>]*>(.*?)</button>',
        html,
        flags=re.S,
    ):
        word_id, definition = match.groups()
        definition_options.append(DefinitionOption(word_id=int(word_id), definition=_strip_tags(definition)))

    action_buttons = re.findall(r'name="action" value="([^"]+)"', html)

    definitions: list[str] = []
    list_match = re.search(r'<ol class="defs">(.*?)</ol>', html, flags=re.S)
    if list_match:
        for li in re.findall(r"<li>(.*?)</li>", list_match.group(1), flags=re.S):
            definitions.append(_strip_tags(li))

    return CardState(
        task_type=task_type,
        word=word,
        gap_text=gap_text,
        fill_choices=fill_choices,
        definition_options=definition_options,
        action_buttons=action_buttons,
        definitions=definitions,
    )


def _rank_action(label: str) -> int:
    normalized = label.lower()
    if any(token in normalized for token in ("perfect", "learned", "easy", "good")):
        return 3
    if any(token in normalized for token in ("ok", "medium")):
        return 2
    if any(token in normalized for token in ("hard", "again", "not learned")):
        return 1
    return 2


def _apply_text_mistake(word: str, profile: LearnerProfile) -> str:
    if not word:
        return word
    if profile.error_style == "missing_vowel":
        result = re.sub(r"[aeiou]", "", word, count=1, flags=re.I)
        return result or word
    if profile.error_style == "double_letter":
        idx = len(word) // 2
        return word[:idx] + word[idx:idx + 1] + word[idx:]
    # neighbor_choice style fallback for text answers:
    if len(word) > 2:
        return word[:-1]
    return word


def _decide_with_llm(
    llm: OpenAICompatClient,
    task_type: str,
    state: CardState,
) -> dict[str, Any]:
    system_prompt = (
        "You are helping simulate a CEFR B2 English learner in a vocabulary card app. "
        "Return JSON only."
    )

    if task_type == "which_definition":
        options = [{"word_id": opt.word_id, "definition": opt.definition} for opt in state.definition_options]
        user_prompt = json.dumps(
            {
                "task": "choose_word_id",
                "word": state.word,
                "options": options,
                "schema": {"best_word_id": "int", "confidence": "0..1", "reason": "short string"},
            },
            ensure_ascii=False,
        )
        return llm.chat_json(system_prompt, user_prompt)

    if task_type == "fill_gap":
        user_prompt = json.dumps(
            {
                "task": "fill_gap",
                "gap_text": state.gap_text,
                "choices": state.fill_choices,
                "schema": {"best_answer": "string", "confidence": "0..1", "reason": "short string"},
            },
            ensure_ascii=False,
        )
        return llm.chat_json(system_prompt, user_prompt)

    user_prompt = json.dumps(
        {
            "task": "flashcard_confidence",
            "word": state.word,
            "definitions": state.definitions[:2],
            "schema": {"know_probability": "0..1", "reason": "short string"},
        },
        ensure_ascii=False,
    )
    return llm.chat_json(system_prompt, user_prompt)


def decide_submission(
    llm: OpenAICompatClient,
    profile: LearnerProfile,
    state: CardState,
    turn_index: int,
) -> dict[str, Any]:
    llm_raw = _decide_with_llm(llm, state.task_type, state)
    made_mistake = profile.should_make_mistake(turn_index, state.task_type)
    decision: dict[str, Any] = {
        "task_type": state.task_type,
        "mistake_applied": made_mistake,
        "llm_raw": llm_raw,
    }

    if state.task_type == "which_definition":
        all_ids = [opt.word_id for opt in state.definition_options]
        predicted = int(llm_raw.get("best_word_id", all_ids[0] if all_ids else -1))
        if predicted not in all_ids and all_ids:
            predicted = all_ids[0]
        final = predicted
        if made_mistake and len(all_ids) > 1:
            idx = all_ids.index(predicted)
            final = all_ids[(idx + profile.wrong_option_offset) % len(all_ids)]
        decision["submitted_answer"] = str(final)
        decision["confidence"] = float(llm_raw.get("confidence", 0.5))
        return decision

    if state.task_type == "fill_gap":
        if state.fill_choices:
            predicted = str(llm_raw.get("best_answer", state.fill_choices[0])).strip()
            if predicted not in state.fill_choices:
                predicted = state.fill_choices[0]
            final = predicted
            if made_mistake and len(state.fill_choices) > 1:
                idx = state.fill_choices.index(predicted)
                final = state.fill_choices[(idx + profile.wrong_option_offset) % len(state.fill_choices)]
            decision["submitted_answer"] = final
            decision["confidence"] = float(llm_raw.get("confidence", 0.5))
            return decision

        predicted = str(llm_raw.get("best_answer", "")).strip()
        final_text = _apply_text_mistake(predicted, profile) if made_mistake else predicted
        decision["submitted_answer"] = final_text
        decision["confidence"] = float(llm_raw.get("confidence", 0.5))
        return decision

    actions = sorted(state.action_buttons, key=lambda x: (_rank_action(x), x))
    if not actions:
        raise ValueError("No action buttons found for flashcard task.")
    confidence = _clamp(float(llm_raw.get("know_probability", 0.5)) + profile.confidence_shift, 0.0, 1.0)

    if confidence >= 0.75:
        idx = len(actions) - 1
    elif confidence >= 0.45:
        idx = max(0, len(actions) // 2)
    else:
        idx = 0

    if made_mistake and profile.randomizer.random() < profile.action_under_rate:
        idx = max(0, idx - 1)
    decision["submitted_action"] = actions[idx]
    decision["confidence"] = confidence
    return decision


def _pick_first_pack_id(home_html: str) -> int | None:
    match = re.search(r'name="pack_id" value="(\d+)"', home_html)
    return int(match.group(1)) if match else None


def start_session(client: httpx.Client, cfg: RunnerConfig) -> None:
    if cfg.pack_id is not None:
        response = client.post(
            "/start",
            data={"pack_id": str(cfg.pack_id), "preset_name": cfg.preset_name},
            follow_redirects=False,
        )
        if response.status_code not in (302, 303):
            raise RuntimeError(f"/start failed: {response.status_code} {response.text}")
        return

    response = client.post(
        "/start-random",
        data={"preset_name": cfg.preset_name},
        follow_redirects=False,
    )
    if response.status_code in (302, 303):
        return

    # fallback when random pool is empty
    home = client.get("/", follow_redirects=False)
    if home.status_code != 200:
        raise RuntimeError(f"Failed to fetch / for fallback start: {home.status_code}")
    first_pack_id = _pick_first_pack_id(home.text)
    if first_pack_id is None:
        raise RuntimeError("No packs found for fallback session start.")
    fallback = client.post(
        "/start",
        data={"pack_id": str(first_pack_id), "preset_name": cfg.preset_name},
        follow_redirects=False,
    )
    if fallback.status_code not in (302, 303):
        raise RuntimeError(f"Fallback /start failed: {fallback.status_code} {fallback.text}")


def read_sid_events(logs_path: Path, sid: str, since_ts: datetime) -> list[dict[str, Any]]:
    if not logs_path.exists():
        return []
    events: list[dict[str, Any]] = []
    with logs_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("sid") != sid:
                continue
            ts_raw = event.get("ts")
            if not isinstance(ts_raw, str):
                continue
            try:
                ts = datetime.fromisoformat(ts_raw)
            except ValueError:
                continue
            if ts >= since_ts:
                events.append(event)
    return events


def run_session(
    cfg: RunnerConfig,
    llm: OpenAICompatClient,
    session_index: int,
) -> list[dict[str, Any]]:
    session_seed = cfg.seed + session_index
    profile = build_profile(session_seed)
    run_started = datetime.now(timezone.utc)

    rows: list[dict[str, Any]] = []
    with httpx.Client(base_url=cfg.app_url, timeout=cfg.timeout_seconds) as client:
        probe = client.get("/", follow_redirects=False)
        if probe.status_code != 200:
            raise RuntimeError(f"App is not reachable at {cfg.app_url}. GET / => {probe.status_code}")

        start_session(client, cfg)
        sid = client.cookies.get("sid") or ""

        if cfg.verbose:
            print(f"[session {session_index}] sid={sid or 'n/a'} profile={profile.learner_id}")

        turns_done = 0
        for turn in range(1, cfg.turns_per_session + 1):
            card_response = client.get("/card", follow_redirects=False)
            if card_response.status_code in (302, 303):
                location = card_response.headers.get("location", "")
                if location == "/done":
                    break
                if location == "/":
                    raise RuntimeError("Session lost active pack unexpectedly.")
                raise RuntimeError(f"Unexpected redirect from /card to {location!r}")
            if card_response.status_code != 200:
                raise RuntimeError(f"/card failed: {card_response.status_code}")

            state = parse_card_state(card_response.text)
            decision = decide_submission(llm, profile, state, turn)

            submission_result: dict[str, Any] = {}
            if state.task_type == "flashcard":
                action = str(decision["submitted_action"])
                post_response = client.post(
                    "/card/action",
                    data={"action": action},
                    follow_redirects=False,
                )
                if post_response.status_code not in (302, 303):
                    raise RuntimeError(f"/card/action failed: {post_response.status_code} {post_response.text}")
                submission_result = {"redirect_to": post_response.headers.get("location", "")}
            else:
                answer = str(decision["submitted_answer"])
                post_response = client.post(
                    "/card/task-response",
                    data={"answer": answer},
                    follow_redirects=False,
                )
                if post_response.status_code != 200:
                    raise RuntimeError(f"/card/task-response failed: {post_response.status_code} {post_response.text}")
                submission_result = post_response.json()

            row = {
                "record_type": "interaction",
                "ts": _now_iso(),
                "session_index": session_index,
                "turn_index": turn,
                "sid": sid,
                "learner_profile": {
                    "learner_id": profile.learner_id,
                    "error_style": profile.error_style,
                    "base_error_rate": round(profile.base_error_rate, 4),
                    "confidence_shift": round(profile.confidence_shift, 4),
                    "wrong_option_offset": profile.wrong_option_offset,
                },
                "task_type": state.task_type,
                "word": state.word,
                "gap_text": state.gap_text,
                "fill_choices": state.fill_choices,
                "definition_options": [vars(opt) for opt in state.definition_options],
                "actions": state.action_buttons,
                "decision": decision,
                "server_result": submission_result,
            }
            rows.append(row)
            turns_done += 1
            if cfg.delay_ms:
                time.sleep(cfg.delay_ms / 1000.0)

        event_rows = read_sid_events(cfg.logs_path, sid, run_started) if sid else []
        event_counts: dict[str, int] = {}
        for event in event_rows:
            name = str(event.get("event", "unknown"))
            event_counts[name] = event_counts.get(name, 0) + 1
        rows.append(
            {
                "record_type": "session_summary",
                "ts": _now_iso(),
                "session_index": session_index,
                "sid": sid,
                "turns_done": turns_done,
                "event_counts": event_counts,
            }
        )
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    cfg = RunnerConfig.from_args()
    llm = OpenAICompatClient(cfg)
    all_rows: list[dict[str, Any]] = []

    try:
        for session_index in range(1, cfg.sessions + 1):
            session_rows = run_session(cfg, llm, session_index=session_index)
            all_rows.extend(session_rows)
            if cfg.verbose:
                summaries = [r for r in session_rows if r.get("record_type") == "session_summary"]
                if summaries:
                    print(f"[session {session_index}] summary={summaries[0]}")
    finally:
        llm.close()

    write_jsonl(cfg.output_path, all_rows)
    print(f"Wrote {len(all_rows)} records to {cfg.output_path}")
    print(f"Model: {cfg.openai_model}")
    print(f"OpenAI-compatible endpoint: {cfg.openai_base_url}")


if __name__ == "__main__":
    main()
