from __future__ import annotations

from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def _nlp() -> Any:
    import spacy
    return spacy.load("en_core_web_sm", disable=["ner", "parser"])


def warmup() -> None:
    _nlp()


def lemmatize(text: str) -> tuple[str, str | None]:
    """Lemmatize a single token (or short span). Returns (lemma, POS).

    For multi-token input, returns the lemma of the first content-bearing token.
    """
    text = (text or "").strip()
    if not text:
        return ("", None)
    doc = _nlp()(text)
    for tok in doc:
        if tok.is_alpha:
            return (tok.lemma_.lower(), tok.pos_)
    return (text.lower(), None)


def lemmatize_chunk(text: str) -> list[tuple[str, str, int, int]]:
    """Tokenize a full chunk. Returns [(lemma, pos, char_start, char_end), ...]."""
    doc = _nlp()(text or "")
    return [(tok.lemma_.lower(), tok.pos_, tok.idx, tok.idx + len(tok.text)) for tok in doc]
