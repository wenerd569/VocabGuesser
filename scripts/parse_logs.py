#!/usr/bin/env python3
"""
Parse logs/logs.jsonl into a flat CSV suitable for Pandas EDA.

Usage:
    python scripts/parse_logs.py --log logs/logs.jsonl --out /tmp/events.csv

Output columns (all events):
    ts, sid, event, pack_id, preset_name, word_id, action, delta,
    new_familiarity, removed, task_type, correct, correct_word,
    learned_count, mark, usefulness, comfort, speed,
    algo_version (present only if logged)

Only the columns relevant to each event are populated; the rest are empty.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

COLUMNS = [
    "ts", "sid", "event",
    "pack_id", "preset_name",
    "word_id", "action", "delta", "new_familiarity", "removed",
    "task_type", "correct", "correct_word",
    "learned_count",
    "mark",
    "usefulness", "comfort", "speed",
    "word_count", "reset",
    "algo_version",
    "exercise_type", "exercise_id", "regeneration_count", "is_custom",
    "error_type", "where",
    "target_mb",
]


def parse(log_path: Path) -> list[dict]:
    rows: list[dict] = []
    with log_path.open(encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError as exc:
                print(f"WARN: line {lineno} is not valid JSON — {exc}", file=sys.stderr)
                continue
            row = {col: entry.get(col, "") for col in COLUMNS}
            rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert logs.jsonl to CSV")
    parser.add_argument("--log", default="logs/logs.jsonl", help="Path to logs.jsonl")
    parser.add_argument("--out", default="-", help="Output CSV path (default: stdout)")
    parser.add_argument(
        "--events", nargs="*", default=None,
        help="Filter to specific event types (e.g. word_action_applied task_response)",
    )
    args = parser.parse_args()

    log_path = Path(args.log)
    if not log_path.exists():
        sys.exit(f"Log file not found: {log_path}")

    rows = parse(log_path)
    if args.events:
        rows = [r for r in rows if r["event"] in args.events]

    if args.out == "-":
        out = sys.stdout
    else:
        out = open(args.out, "w", newline="", encoding="utf-8")  # noqa: SIM115

    try:
        writer = csv.DictWriter(out, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if args.out != "-":
            out.close()

    if args.out != "-":
        print(f"Written {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
