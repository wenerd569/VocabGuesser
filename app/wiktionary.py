from __future__ import annotations

import re
from dataclasses import dataclass

import httpx


@dataclass
class Sense:
    pos: str
    text: str

    def to_dict(self) -> dict:
        return {"pos": self.pos, "text": self.text}


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html(s: str) -> str:
    return _WS_RE.sub(" ", _HTML_TAG_RE.sub("", s or "")).strip()


def _normalize_pos(raw: str) -> str:
    raw = (raw or "").lower()
    if raw.startswith("noun"):
        return "noun"
    if raw.startswith("verb"):
        return "verb"
    if raw.startswith("adjective") or raw == "adj":
        return "adjective"
    return raw


class WiktionaryClient:
    def __init__(self, timeout: float = 4.0):
        self.base = "https://en.wiktionary.org/api/rest_v1/page/definition"
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "VocFlow/0.1 (English vocab learning app)"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch(self, lemma: str, max_senses: int = 7) -> list[Sense]:
        """Return up to `max_senses` English senses, prioritising noun > verb > adjective.

        Returns [] on 404 or empty English section.
        """
        url = f"{self.base.rstrip('/')}/{lemma}"
        try:
            resp = await self._client.get(url)
        except httpx.HTTPError:
            return []
        print(resp)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        en_sections = data.get("en") or []

        senses: list[Sense] = []
        for section in en_sections:
            pos = _normalize_pos(section.get("partOfSpeech", ""))
            for d in section.get("definitions", []):
                definition = _strip_html(d.get("definition", ""))
                if definition:
                    senses.append(Sense(pos=pos, text=definition))

        return senses[:max_senses]
