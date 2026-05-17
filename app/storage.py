from __future__ import annotations

import asyncio
import json
import os
import random
from dataclasses import dataclass, field
from pathlib import Path

from .config import (
    MAX_ACTIONS,
    MAX_DEFINITIONS_PER_WORD,
    MIN_ACTIONS,
    PACKS_PATH,
    PRESETS_PATH,
    WORDS_PATH,
)
from .lemmatize import lemmatize
from .wiktionary import Sense, WiktionaryClient


@dataclass
class Word:
    word_id: int
    word: str
    eng_definitions: list[Sense] = field(default_factory=list)
    known: bool = False

    def to_dict(self) -> dict:
        return {
            "word_id": self.word_id,
            "word": self.word,
            "eng_definitions": [d.to_dict() for d in self.eng_definitions],
            "known": self.known,
        }


@dataclass(frozen=True)
class Pack:
    pack_id: int
    pack_name: str
    word_ids: tuple[int, ...]


@dataclass
class Preset:
    preset_name: str
    actions: dict[str, float] = field(default_factory=dict)


def _parse_sense(raw: dict, where: str) -> Sense:
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: definition entry must be an object")

    pos = raw.get("pos") or raw.get("part_of_speech") or ""
    txt = raw.get("text", "")
    example = raw.get("example", "")

    if not isinstance(pos, str) or not isinstance(txt, str) or not isinstance(example, str):
        raise ValueError(f"{where}: pos, text and example must be strings")

    return Sense(pos=pos, text=txt, example=example)


def _parse_word(raw: dict, where: str) -> Word:
    eng_raw = raw.get("eng_definitions")
    # Backwards compat: old single-string format.
    if eng_raw is None and "eng_definition" in raw:
        eng_raw = [{"pos": "", "text": raw["eng_definition"]}]
    eng_raw = eng_raw or []
    if not isinstance(eng_raw, list):
        raise ValueError(f"{where}: eng_definitions must be a list")
    if len(eng_raw) > MAX_DEFINITIONS_PER_WORD:
        raise ValueError(f"{where}: more than {MAX_DEFINITIONS_PER_WORD} definitions")
    return Word(
        word_id=int(raw["word_id"]),
        word=str(raw["word"]),
        eng_definitions=[_parse_sense(d, where) for d in eng_raw],
        known=bool(raw.get("known", False)),
    )


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Required data file missing: {path}")
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"Malformed JSON at {path}:{lineno}: {e}") from e
    return rows


def _load_presets() -> list[Preset]:
    if not PRESETS_PATH.exists():
        raise FileNotFoundError(f"Required presets file missing: {PRESETS_PATH}")
    try:
        raw = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed JSON in {PRESETS_PATH}: {e}") from e
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{PRESETS_PATH} must contain a non-empty JSON array")
    presets: list[Preset] = []
    seen: set[str] = set()
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"Preset #{idx} must be an object")
        name = item.get("preset_name")
        actions = item.get("actions")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Preset #{idx} missing valid preset_name")
        if not isinstance(actions, dict):
            raise ValueError(f"Preset {name!r} missing actions dict")
        if not (MIN_ACTIONS <= len(actions) <= MAX_ACTIONS):
            raise ValueError(
                f"Preset {name!r} must have {MIN_ACTIONS}–{MAX_ACTIONS} actions, got {len(actions)}"
            )
        clean: dict[str, float] = {}
        for k, v in actions.items():
            if not isinstance(k, str) or not k.strip():
                raise ValueError(f"Preset {name!r} has an empty action name")
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise ValueError(f"Preset {name!r} action {k!r} must be numeric")
            clean[k] = float(v)
        if name in seen:
            raise ValueError(f"Duplicate preset_name: {name}")
        seen.add(name)
        presets.append(Preset(preset_name=name, actions=clean))
    return presets


class Storage:
    def __init__(
        self,
        words: dict[int, Word],
        packs: dict[int, Pack],
        presets: list[Preset],
        max_word_id: int,
    ) -> None:
        self.words = words
        self.packs = packs
        self.presets = presets
        self._presets_by_name = {p.preset_name: p for p in presets}
        self._lock = asyncio.Lock()
        self._max_word_id = max_word_id
        self.wikibase = WiktionaryClient()

    @classmethod
    def load(cls) -> "Storage":
        words, max_id = cls._load_words_with_compaction()
        packs = cls._load_packs(words)
        presets = _load_presets()
        return cls(words=words, packs=packs, presets=presets, max_word_id=max_id)

    @staticmethod
    def _load_words_with_compaction() -> tuple[dict[int, Word], int]:
        """Load all words from JSONL (last-wins), skip those with no definitions,
        compact the file with only the words that have definitions, return them."""
        if not WORDS_PATH.exists():
            WORDS_PATH.parent.mkdir(parents=True, exist_ok=True)
            WORDS_PATH.touch()
            return {}, 0

        all_words: dict[int, Word] = {}
        for lineno, raw in enumerate(_load_jsonl(WORDS_PATH), start=1):
            w = _parse_word(raw, f"{WORDS_PATH}:{lineno}")
            all_words[w.word_id] = w  # last entry per word_id wins

        # Track max id across ALL words seen (including skipped ones) so we
        # never reuse an id that was previously issued.
        max_id = max(all_words.keys()) if all_words else 0

        active = {wid: w for wid, w in all_words.items() if w.eng_definitions}
        Storage._compact(active)
        return active, max_id

    @staticmethod
    def _compact(words: dict[int, Word]) -> None:
        WORDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = WORDS_PATH.parent / (WORDS_PATH.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for w in sorted(words.values(), key=lambda x: x.word_id):
                f.write(json.dumps(w.to_dict(), ensure_ascii=False) + "\n")
        os.replace(tmp, WORDS_PATH)

    @staticmethod
    def _load_packs(words: dict[int, Word]) -> dict[int, Pack]:
        packs: dict[int, Pack] = {}
        for lineno, raw in enumerate(_load_jsonl(PACKS_PATH), start=1):
            p = Pack(
                pack_id=raw["pack_id"],
                pack_name=raw["pack_name"],
                word_ids=tuple(raw["word_ids"]),
            )
            if p.pack_id in packs:
                raise ValueError(f"Duplicate pack_id: {p.pack_id}")
            for wid in p.word_ids:
                if wid not in words:
                    raise ValueError(
                        f"Pack {p.pack_id} references unknown word_id {wid} (line {lineno})"
                    )
            packs[p.pack_id] = p
        return packs

    # ---- read accessors --------------------------------------------------

    def list_packs(self) -> list[Pack]:
        return sorted(self.packs.values(), key=lambda p: p.pack_id)

    def get_pack(self, pack_id: int) -> Pack | None:
        return self.packs.get(pack_id)

    def get_word(self, word_id: int) -> Word | None:
        return self.words.get(word_id)

    def list_words(self) -> list[Word]:
        return sorted(self.words.values(), key=lambda w: w.word_id, reverse=True)

    def list_presets(self) -> list[Preset]:
        return list(self.presets)

    def get_preset(self, name: str) -> Preset | None:
        return self._presets_by_name.get(name)

    def default_preset(self) -> Preset:
        return self.presets[0]

    def find_word_by_text(self, text: str) -> Word | None:
        needle = text.strip().lower()
        if not needle:
            return None
        for w in self.words.values():
            if w.word.lower() == needle:
                return w
        return None

    # ---- write operations ------------------------------------------------

    def _next_word_id_locked(self) -> int:
        self._max_word_id += 1
        return self._max_word_id

    def _append_word_locked(self, w: Word) -> None:
        WORDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with WORDS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(w.to_dict(), ensure_ascii=False) + "\n")

    def sample_unknown(self, n: int = 7) -> list[Word]:
        pool = [w for w in self.words.values() if not w.known]
        return random.sample(pool, min(n, len(pool)))

    async def add_word(self, text: str) -> tuple[Word | None, str]:
        """Fetch definition from Wiktionary and add the word.

        Returns (word, status) where status is one of:
        - "created"   – word added with definitions
        - "duplicate" – already in dictionary (returned as-is)
        - "not_found" – Wiktionary returned no definitions; word not added
        """
        text = text.strip()
        if not text:
            raise ValueError("Empty word")
        lemma, _ = lemmatize(text)
        text = lemma or text
        definitions = await self.wikibase.fetch(text)
        if not definitions:
            return None, "not_found"
        async with self._lock:
            existing = self.find_word_by_text(text)
            if existing is not None:
                return existing, "duplicate"
            word = Word(word_id=self._next_word_id_locked(), word=text, eng_definitions=definitions)
            self.words[word.word_id] = word
            self._append_word_locked(word)
            return word, "created"

    async def add_words_bulk(
        self, texts: list[str]
    ) -> tuple[list[Word], list[str], list[str]]:
        """Returns (added, duplicates, not_found).

        Fetches each word from Wiktionary sequentially. Words with no Wiktionary
        entry are skipped and reported in not_found.
        """
        added: list[Word] = []
        duplicates: list[str] = []
        not_found: list[str] = []
        for raw in texts:
            t = raw.strip()
            if not t:
                continue
            lemma, _ = lemmatize(t)
            t = lemma or t
            definitions = await self.wikibase.fetch(t)
            if not definitions:
                not_found.append(t)
                continue
            async with self._lock:
                existing = self.find_word_by_text(t)
                if existing is not None:
                    duplicates.append(t)
                    continue
                word = Word(word_id=self._next_word_id_locked(), word=t, eng_definitions=definitions)
                self.words[word.word_id] = word
                self._append_word_locked(word)
                added.append(word)
        return added, duplicates, not_found

    async def set_known(self, word_id: int, known: bool) -> Word | None:
        async with self._lock:
            w = self.words.get(word_id)
            if w is None:
                return None
            w.known = known
            self._append_word_locked(w)
            return w
