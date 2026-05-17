"""LLM-based word scheduler for algo_version=v2_llm.
pick_next_word() is a synchronous function; call it via asyncio.to_thread
from FastAPI route handlers.
"""
from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING

from groq import Groq

from .config import SCHEDULER_MODEL, SCHEDULER_TIMEOUT

if TYPE_CHECKING:
    from .state import AnswerRecord, WordInfo
    from .storage import Word

logger = logging.getLogger(__name__)

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY", "")
        _client = Groq(api_key=api_key)
    return _client


def _build_prompt(
    history: list[AnswerRecord],
    remaining_ids: list[int],
    word_store: dict[int, Word],
    word_info: dict[int, WordInfo],
) -> str:
    lines: list[str] = [
        "You are a spaced-repetition scheduler for an English vocabulary learning app.\n",
    ]

    if history:
        lines.append("## Session history (oldest → newest, last 20 events)")
        lines.append("| word | task | outcome | familiarity_after |")
        lines.append("|------|------|---------|------------------|")
        for rec in history[-20:]:
            w = word_store.get(rec.word_id)
            word_str = w.word if w else f"id:{rec.word_id}"
            if rec.correct is True:
                outcome = "correct"
            elif rec.correct is False:
                outcome = "wrong"
            else:
                outcome = rec.action
            fam_str = f"{rec.familiarity_after:.2f}"
            if rec.familiarity_after >= 1.0:
                fam_str += " ✓"
            lines.append(f"| {word_str} | {rec.task_type} | {outcome} | {fam_str} |")
        lines.append("")
    else:
        lines.append("## Session history\nNo history yet — this is the first card.\n")

    lines.append("## Remaining pool (words not yet graduated)")
    lines.append("| word_id | word | familiarity | shows |")
    lines.append("|---------|------|-------------|-------|")
    for wid in remaining_ids:
        w = word_store.get(wid)
        if w is None:
            continue
        info = word_info.get(wid)
        fam = round(info.familiarity, 2) if info else 0.0
        shows = info.shows if info else 0
        lines.append(f"| {wid} | {w.word} | {fam} | {shows} |")
    lines.append("")

    lines.append("## Goal")
    lines.append(
        "Maximize long-term retention while keeping cognitive load manageable. "
        "Apply spaced repetition principles: prioritize words with recent errors "
        "or low familiarity. Avoid repeating the same word twice in a row "
        "if alternatives exist. Words close to the graduation threshold (familiarity ≥ 1.0) "
        "should be shown soon to lock in the memory."
    )
    lines.append("")
    lines.append(
        'Return ONLY valid JSON with no explanation: {"word_id": <integer from the remaining pool>}'
    )

    return "\n".join(lines)


def _build_fallback_prompt(
    remaining_ids: list[int],
    word_store: dict[int, Word],
    last_word_id: int | None,
) -> str:
    candidates = [wid for wid in remaining_ids if wid != last_word_id] or remaining_ids
    words_str = ", ".join(
        f"{wid}={word_store[wid].word}" for wid in candidates if wid in word_store
    )
    return (
        f"Pick one vocabulary word for a spaced-repetition session. "
        f"Available word_ids: {words_str}. "
        f'Return ONLY JSON: {{"word_id": <integer>}}'
    )


def pick_next_word(
    history: list[AnswerRecord],
    remaining_ids: list[int],
    word_store: dict[int, Word],
    word_info: dict[int, WordInfo],
) -> int | None:
    """Return the word_id the LLM recommends showing next.

    Returns None if both attempts fail; caller should fall back to FIFO.
    """
    if not remaining_ids:
        return None
    if len(remaining_ids) == 1:
        return remaining_ids[0]

    client = _get_client()
    last_word_id = history[-1].word_id if history else None

    for attempt in range(2):
        try:
            if attempt == 0:
                prompt = _build_prompt(history, remaining_ids, word_store, word_info)
            else:
                prompt = _build_fallback_prompt(remaining_ids, word_store, last_word_id)

            resp = client.chat.completions.create(
                model=SCHEDULER_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                timeout=SCHEDULER_TIMEOUT,
                max_tokens=32,
            )
            raw = resp.choices[0].message.content or ""
            data = json.loads(raw)
            wid = int(data["word_id"])
            if wid in remaining_ids:
                return wid
            logger.warning("Scheduler returned word_id=%d not in remaining pool", wid)
        except Exception as exc:
            logger.warning("Scheduler attempt %d failed: %s", attempt + 1, exc)

    return None
