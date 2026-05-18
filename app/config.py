from __future__ import annotations

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
DATA_DIR    = Path(os.getenv("DATA_DIR", "/app/data"))
PRESETS_DIR = Path(os.getenv("PRESETS_DIR", "/app/presets"))
LOGS_DIR    = Path(os.getenv("LOGS_DIR", "/app/logs"))

PACKS_PATH   = DATA_DIR    / "packs.jsonl"
WORDS_PATH   = DATA_DIR    / "words.jsonl"
PRESETS_PATH = PRESETS_DIR / "progress.json"
CHUNKS_DB    = DATA_DIR    / "chunks.db"
LOG_PATH     = LOGS_DIR    / "logs.jsonl"

# ── Storage limits ─────────────────────────────────────────────────────────
MIN_ACTIONS            = 2
MAX_ACTIONS            = 5
MAX_DEFINITIONS_PER_WORD = 10

# ── Chunk ingestion ────────────────────────────────────────────────────────
MIN_CHUNK_CHARS = 40
MAX_CHUNK_CHARS = 600

# ── Session / learning thresholds ─────────────────────────────────────────
LEARNED_THRESHOLD = 1.0
SHOWS_THRESHOLD   = 7

# ── Packs ─────────────────────────────────────────────────────────────────
RANDOM_PACK_ID   = 0
RANDOM_PACK_SIZE = 7

# ── UI ────────────────────────────────────────────────────────────────────
PAGE_SIZE = 20

# ── Scheduler (LLM-based word selection) ──────────────────────────────────
ALGO_VERSION = os.environ.get("ALGO_VERSION", "v1_legacy")
SCHEDULER_MODEL = os.environ.get("SCHEDULER_MODEL", "llama-3.1-8b-instant")
SCHEDULER_TIMEOUT = float(os.environ.get("SCHEDULER_TIMEOUT", "8"))
