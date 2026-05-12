"""Chunk store: SQLite-backed inverted index mapping word_ids → text chunks.

The store only keeps chunks that contain at least one tracked word so the
database stays lean even after large Wikipedia ingestion runs.
"""
from __future__ import annotations

import re
import sqlite3
import threading
from typing import Any

from .config import CHUNKS_DB, MIN_CHUNK_CHARS, MAX_CHUNK_CHARS

DB_PATH = CHUNKS_DB

# Sentence splitter (lightweight, no spaCy needed here)
_SENT_END = re.compile(r'(?<=[.!?])\s+(?=[A-Z"\'])')

# Shared load-progress state (written by background thread, read by status endpoint)
LOAD_STATUS: dict[str, Any] = {
    "running": False,
    "done_bytes": 0,
    "target_bytes": 0,
    "chunks_added": 0,
    "error": None,
}
_load_lock = threading.Lock()


def _split_chunks(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    sentences = [s.strip() for s in _SENT_END.split(text) if s.strip()]
    return [s for s in sentences if MIN_CHUNK_CHARS <= len(s) <= MAX_CHUNK_CHARS]


def _find_word_ids(text: str, word_map: dict[str, int]) -> list[int]:
    """Return word_ids whose base form appears as a word token in text."""
    lower = text.lower()
    return [wid for word, wid in word_map.items() if re.search(r"\b" + re.escape(word) + r"\b", lower)]


class ChunkStore:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self._path = db_path
        self._local = threading.local()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(str(self._path), check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS chunks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                text        TEXT    NOT NULL,
                source      TEXT    NOT NULL DEFAULT '',
                byte_size   INTEGER NOT NULL DEFAULT 0
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
                USING fts5(text, tokenize='porter unicode61');
            CREATE TABLE IF NOT EXISTS word_chunks (
                word_id  INTEGER NOT NULL,
                chunk_id INTEGER NOT NULL,
                PRIMARY KEY (word_id, chunk_id)
            );
            CREATE INDEX IF NOT EXISTS idx_wc_word ON word_chunks(word_id);
        """)
        # Backfill FTS if chunks exist but FTS is empty (e.g. after schema migration)
        n_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        n_fts    = conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
        if n_chunks > 0 and n_fts == 0:
            conn.execute("INSERT INTO chunks_fts(rowid, text) SELECT id, text FROM chunks")
        conn.commit()

    # ── read ──────────────────────────────────────────────────────────────────

    def get_chunk_for_word(self, word_id: int) -> str | None:
        row = self._conn().execute(
            """
            SELECT c.text FROM chunks c
            JOIN word_chunks wc ON wc.chunk_id = c.id
            WHERE wc.word_id = ?
            ORDER BY RANDOM() LIMIT 1
            """,
            (word_id,),
        ).fetchone()
        return row[0] if row else None

    def get_chunks_for_word(self, word_id: int, limit: int = 5) -> list[str]:
        rows = self._conn().execute(
            """
            SELECT c.text FROM chunks c
            JOIN word_chunks wc ON wc.chunk_id = c.id
            WHERE wc.word_id = ?
            ORDER BY RANDOM() LIMIT ?
            """,
            (word_id, limit),
        ).fetchall()
        return [r[0] for r in rows]

    def chunk_counts(self, word_ids: list[int]) -> dict[int, int]:
        counts = {wid: 0 for wid in word_ids}
        if not word_ids:
            return counts
        placeholders = ",".join("?" * len(word_ids))
        rows = self._conn().execute(
            f"SELECT word_id, COUNT(*) FROM word_chunks WHERE word_id IN ({placeholders}) GROUP BY word_id",
            word_ids,
        ).fetchall()
        for wid, n in rows:
            counts[wid] = n
        return counts

    def total_chunks(self) -> int:
        return self._conn().execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    def total_bytes(self) -> int:
        return self._conn().execute(
            "SELECT COALESCE(SUM(byte_size),0) FROM chunks"
        ).fetchone()[0]

    def coverage_stats(self, word_ids: list[int]) -> dict:
        """Return coverage info for the given word_id list."""
        if not word_ids:
            return {"covered": 0, "total": 0, "histogram": {}}
        conn = self._conn()
        histogram: dict[int, int] = {}
        covered = 0
        for wid in word_ids:
            n = conn.execute(
                "SELECT COUNT(*) FROM word_chunks WHERE word_id=?", (wid,)
            ).fetchone()[0]
            histogram[wid] = n
            if n:
                covered += 1
        return {"covered": covered, "total": len(word_ids), "histogram": histogram}

    # ── write ─────────────────────────────────────────────────────────────────

    def add_chunks_bulk(self, records: list[tuple[str, str, list[int]]]) -> int:
        """Insert (text, source, [word_id, …]) triples. Returns count added."""
        conn = self._conn()
        added = 0
        for text, source, word_ids in records:
            if not word_ids:
                continue
            cur = conn.execute(
                "INSERT INTO chunks(text,source,byte_size) VALUES(?,?,?)",
                (text, source, len(text.encode())),
            )
            chunk_id = cur.lastrowid
            conn.execute("INSERT INTO chunks_fts(rowid,text) VALUES(?,?)", (chunk_id, text))
            conn.executemany(
                "INSERT OR IGNORE INTO word_chunks(word_id,chunk_id) VALUES(?,?)",
                [(wid, chunk_id) for wid in word_ids],
            )
            added += 1
        conn.commit()
        return added

    def index_word(self, word_id: int, word_text: str) -> int:
        """Search existing chunks via FTS and create word_chunks entries for a new word.

        Returns the number of chunks matched.
        """
        if not word_text.strip():
            return 0
        conn = self._conn()
        try:
            # Exact-phrase FTS match (quotes = phrase, not prefix)
            rows = conn.execute(
                'SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ?',
                (f'"{word_text.lower()}"',),
            ).fetchall()
        except Exception:
            return 0
        if not rows:
            return 0
        conn.executemany(
            "INSERT OR IGNORE INTO word_chunks(word_id,chunk_id) VALUES(?,?)",
            [(word_id, row[0]) for row in rows],
        )
        conn.commit()
        return len(rows)


# ── background loader ─────────────────────────────────────────────────────────

def start_load(store: ChunkStore, words: dict[int, str], target_mb: int = 100) -> None:
    """Kick off a background thread streaming Wikipedia into the chunk store.

    `words` maps word_id → lemmatized word text.
    Only chunks containing at least one word are stored.
    """
    with _load_lock:
        if LOAD_STATUS["running"]:
            return
        LOAD_STATUS.update({
            "running": True,
            "done_bytes": 0,
            "target_bytes": target_mb * 1_000_000,
            "chunks_added": 0,
            "error": None,
        })

    # Build reverse map: lowercase_word → word_id
    word_map: dict[str, int] = {w.lower(): wid for wid, w in words.items()}

    def _run() -> None:
        try:
            from datasets import load_dataset  # type: ignore
            target_bytes = target_mb * 1_000_000
            done = 0
            batch: list[tuple[str, str, list[int]]] = []

            ds = load_dataset(
                "wikimedia/wikipedia", "20231101.en",
                split="train", streaming=True,
            )
            ds = ds.shuffle(seed=42, buffer_size=5_000)

            for article in ds:
                text = article.get("text", "")
                if len(text) < 500 or "may refer to" in text[:200].lower():
                    continue
                for chunk in _split_chunks(text):
                    matched = _find_word_ids(chunk, word_map)
                    if not matched:
                        continue
                    batch.append((chunk, "wikipedia", matched))
                    done += len(chunk.encode())
                    LOAD_STATUS["done_bytes"] = done
                    if len(batch) >= 500:
                        added = store.add_chunks_bulk(batch)
                        LOAD_STATUS["chunks_added"] += added
                        batch.clear()
                    if done >= target_bytes:
                        break
                if done >= target_bytes:
                    break

            if batch:
                added = store.add_chunks_bulk(batch)
                LOAD_STATUS["chunks_added"] += added
        except Exception as exc:
            LOAD_STATUS["error"] = str(exc)
        finally:
            LOAD_STATUS["running"] = False

    threading.Thread(target=_run, daemon=True, name="wiki-loader").start()
