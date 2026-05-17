#!/usr/bin/env python3
"""
Generate synthetic session data for EDA bootstrapping.

Simulates the legacy circular-queue algorithm with realistic user behaviour
so you can analyse metrics before real users exist.

Usage:
    python scripts/mock_session.py --sessions 50 --words 20 --out logs/mock_logs.jsonl
    python scripts/mock_session.py --sessions 200 --words 15 --preset "Graded (4)" --seed 99

Output: append-only JSONL in the same schema as logs/logs.jsonl.
"""

from __future__ import annotations

import argparse
import json
import random
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configurable user behaviour profiles
# ---------------------------------------------------------------------------

PRESETS: dict[str, dict[str, float]] = {
    "Default": {"learned": 1.0, "not learned": 0.0},
    "Three-step": {"easy": 1.0, "ok": 0.5, "again": 0.0},
    "Graded (4)": {"easy": 1.0, "good": 0.5, "hard": 0.25, "again": 0.0},
    "Five-step": {"perfect": 1.0, "easy": 0.5, "ok": 0.34, "hard": 0.2, "again": 0.0},
}

LEARNED_THRESHOLD = 1.0
SHOWS_THRESHOLD = 7

# Probability that the user gets a task correct given their familiarity with the word.
# Familiarity 0.0 → ~30% correct; 0.75 → ~80% correct.
def _correct_prob(familiarity: float) -> float:
    return min(0.95, 0.30 + familiarity * 0.87)


# How the user distributes their action buttons (weighted by familiarity level).
def _pick_action(actions: dict[str, float], familiarity: float) -> str:
    sorted_actions = sorted(actions.items(), key=lambda kv: kv[1])
    n = len(sorted_actions)
    # Weight towards higher deltas as familiarity grows.
    weights = [(i + 1) * (0.3 + familiarity) for i in range(n)]
    names = [a[0] for a in sorted_actions]
    return random.choices(names, weights=weights, k=1)[0]


# ---------------------------------------------------------------------------
# Simulation core
# ---------------------------------------------------------------------------

def _simulate_session(
    sid: str,
    word_ids: list[int],
    actions: dict[str, float],
    preset_name: str,
    pack_id: int,
    start_ts: datetime,
    rng: random.Random,
) -> list[dict]:
    events: list[dict] = []
    ts = start_ts

    def emit(event: str, **kwargs) -> None:
        nonlocal ts
        events.append({"ts": ts.isoformat(), "sid": sid, "event": event, **kwargs})
        ts += timedelta(seconds=rng.randint(5, 45))

    familiarity: dict[int, float] = {wid: 0.0 for wid in word_ids}
    shows: dict[int, int] = {wid: 0 for wid in word_ids}
    remaining: deque[int] = deque(word_ids)
    learned: set[int] = set()

    emit("pack_started", pack_id=pack_id, preset_name=preset_name,
         actions=actions, reset=True)

    while remaining:
        wid = remaining[0]
        fam = familiarity[wid]

        # Decide: task response or direct action (60/40 split when familiarity is low)
        use_task = rng.random() < (0.6 - fam * 0.3)

        if use_task:
            task_type = rng.choices(
                ["fill_gap", "flashcard", "which_definition"],
                weights=[2, 1, 1], k=1
            )[0]
            correct = rng.random() < _correct_prob(fam)
            delta = max(actions.values()) if correct else min(actions.values())
            familiarity[wid] += delta
            shows[wid] += 1
            removed = familiarity[wid] >= LEARNED_THRESHOLD or shows[wid] >= SHOWS_THRESHOLD
            emit("task_response", pack_id=pack_id, task_type=task_type,
                 correct=correct, correct_word=f"word_{wid}", delta=delta,
                 removed=removed)
        else:
            action = _pick_action(actions, fam)
            delta = actions[action]
            familiarity[wid] += delta
            shows[wid] += 1
            removed = familiarity[wid] >= LEARNED_THRESHOLD or shows[wid] >= SHOWS_THRESHOLD
            emit("word_action_applied", pack_id=pack_id, preset_name=preset_name,
                 word_id=wid, action=action, delta=delta,
                 new_familiarity=round(familiarity[wid], 4), removed=removed)

        remaining.popleft()
        if removed:
            learned.add(wid)
        else:
            remaining.append(wid)

        # Simulate occasional mid-session feedback
        if rng.random() < 0.05:
            mark = rng.choice(["like", "dislike", "confused"])
            emit("pack_marked", pack_id=pack_id, preset_name=preset_name,
                 current_word_id=wid, mark=mark)

    emit("pack_completed", pack_id=pack_id, preset_name=preset_name,
         learned_count=len(learned))

    # End-of-session rating (70% of sessions get rated)
    if rng.random() < 0.70:
        avg_fam = sum(familiarity.values()) / max(len(familiarity), 1)
        base = int(avg_fam * 4) + 1
        emit("pack_rated", pack_id=pack_id, preset_name=preset_name,
             learned_count=len(learned),
             usefulness=min(5, max(1, base + rng.randint(-1, 1))),
             comfort=min(5, max(1, base + rng.randint(-1, 1))),
             speed=min(5, max(1, base + rng.randint(-1, 1))))

    return events


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate mock session JSONL logs")
    parser.add_argument("--sessions", type=int, default=50, help="Number of sessions to simulate")
    parser.add_argument("--words", type=int, default=15, help="Words per session")
    parser.add_argument("--preset", default="Graded (4)", choices=list(PRESETS),
                        help="Preset name to use for all sessions")
    parser.add_argument("--pack-id", type=int, default=1, help="Pack ID to use")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--out", default="logs/mock_logs.jsonl", help="Output JSONL path")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    actions = PRESETS[args.preset]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    all_events: list[dict] = []
    base_ts = datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc)

    for i in range(args.sessions):
        sid = uuid.uuid4().hex
        word_ids = list(range(1, args.words + 1))
        rng.shuffle(word_ids)
        session_ts = base_ts + timedelta(days=i // 3, hours=rng.randint(0, 16))
        events = _simulate_session(
            sid=sid,
            word_ids=word_ids,
            actions=actions,
            preset_name=args.preset,
            pack_id=args.pack_id,
            start_ts=session_ts,
            rng=rng,
        )
        all_events.extend(events)

    with out_path.open("w", encoding="utf-8") as f:
        for ev in all_events:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")

    print(f"Wrote {len(all_events)} events across {args.sessions} sessions to {out_path}")


if __name__ == "__main__":
    main()
