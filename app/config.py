from __future__ import annotations

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
DATA_DIR    = Path("/app/data")
PRESETS_DIR = Path("/app/presets")
LOGS_DIR    = Path("/app/logs")

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
