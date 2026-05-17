from __future__ import annotations

import random
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .config import LEARNED_THRESHOLD, SHOWS_THRESHOLD
from .storage import Pack, Preset


TASK_DELTAS = {
    "which_definition": {
        "correct": 0.4,
        "wrong": 0.0,
    },
    "fill_gap_choice": {
        "correct": 0.6,
        "wrong": 0.0,
    },
    "fill_gap_text": {
        "correct": 1.0,
        "wrong": 0.0,
    },
}

# ── Simple result types ───────────────────────────────────────────────────────

@dataclass
class ActionResult:
    word_id: int
    action: str
    delta: float
    new_familiarity: float | None
    removed: bool


@dataclass
class WordInfo:
    shows: int
    familiarity: float

    def update(self, delta: float) -> None:
        self.shows += 1
        self.familiarity += delta

    def need_to_remove(self) -> bool:
        return self.shows >= SHOWS_THRESHOLD or self.familiarity >= LEARNED_THRESHOLD


# ── Task types ────────────────────────────────────────────────────────────────

@dataclass
class Task:
    """A generated exercise for the current word card."""
    task_type: str          # "flashcard" | "fill_gap" | "which_definition"
    word_id: int
    correct_word: str = ""

    # fill_gap
    display_text: str = ""      # text shown to user (with masked word)
    answer_mode: str = ""       # "choice" | "text"
    choices: list[str] = field(default_factory=list)

    # which_definition: list of {"word": str, "word_id": int, "definition": str}
    definition_options: list[dict] = field(default_factory=list)


@dataclass
class TaskResult:
    correct: bool
    correct_word: str
    task_type: str
    delta: float
    removed: bool


# ── Masking helpers ───────────────────────────────────────────────────────────

def _mask_partial(word: str, squeeze: bool) -> str:
    """Reveal first char + every 3rd internal char + last char; mask the rest."""
    n = len(word)
    if n <= 2:
        return "_" * n
    revealed = {0, n - 1}
    for i in range(3, n - 1, 3):
        revealed.add(i)
    chars = [c if i in revealed else "_" for i, c in enumerate(word)]
    result = "".join(chars)
    if squeeze:
        result = re.sub(r"_+", "_", result)
    return result


def _insert_mask(text: str, word: str, mask: str) -> str | None:
    """Replace the first case-insensitive whole-word occurrence of `word` in text."""
    pattern = re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE)
    if not pattern.search(text):
        return None
    return pattern.sub(mask, text, count=1)


# ── Task generation ───────────────────────────────────────────────────────────

def _generate_task(
    word: Any,          # storage.Word
    other_words: list,  # list[storage.Word] from the session
    chunk: str | None,
    actions: dict[str, float],
    is_first_show: bool = False,
) -> Task:
    """Pick a task type randomly and build a Task for the given word."""
    # Source text: prefer chunk, fall back to first definition sentence
    source_text: str | None = chunk
    if is_first_show:
        return Task(task_type="flashcard", word_id=word.word_id, correct_word=word.word)
    if not source_text and word.eng_definitions:
        source_text = word.eng_definitions[0].text

    # Candidates for which_definition wrong options
    def_candidates = [
        w for w in other_words
        if w.word_id != word.word_id and w.eng_definitions
    ]

    # Determine available task types + weights
    weights: dict[str, float] = {}
    if source_text:
        weights["fill_gap"] = 2.0
    if len(def_candidates) >= 2 and word.eng_definitions:
        weights["which_definition"] = 1.0
    if not weights:
        return Task(task_type="flashcard", word_id=word.word_id, correct_word=word.word)

    task_type = random.choices(
        list(weights.keys()), weights=list(weights.values()), k=1
    )[0]

    # ── flashcard ──────────────────────────────────────────────────────────
    if task_type == "flashcard":
        return Task(task_type="flashcard", word_id=word.word_id, correct_word=word.word)

    # ── fill_gap ───────────────────────────────────────────────────────────
    if task_type == "fill_gap":
        assert source_text is not None
        style = random.choice(["full"]) # random.choice(["full", "partial_squeeze", "partial_no_squeeze"])

        if style == "full":
            mask = "___"
            answer_mode = random.choice(["choice", "text"])
        else:
            mask = _mask_partial(word.word, squeeze=(style == "partial_squeeze"))
            answer_mode = "text"

        display_text = _insert_mask(source_text, word.word, mask)
        if display_text is None:
            # Word not found verbatim — show definition with mask appended
            display_text = f"{source_text}\n\n→ The missing word: {mask}"

        choices: list[str] = []
        if answer_mode == "choice":
            pool = [w.word for w in other_words if w.word_id != word.word_id]
            random.shuffle(pool)
            choices = [word.word] + pool[:min(3, len(pool))]
            random.shuffle(choices)

        return Task(
            task_type="fill_gap",
            word_id=word.word_id,
            correct_word=word.word,
            display_text=display_text,
            answer_mode=answer_mode,
            choices=choices,
        )

    # ── which_definition ───────────────────────────────────────────────────
    correct_def = word.eng_definitions[0].text
    wrong_sample = random.sample(def_candidates, min(3, len(def_candidates)))
    options = [{"word": word.word, "word_id": word.word_id, "definition": correct_def}]
    for w in wrong_sample:
        options.append({
            "word": w.word,
            "word_id": w.word_id,
            "definition": w.eng_definitions[0].text,
        })
    random.shuffle(options)
    return Task(
        task_type="which_definition",
        word_id=word.word_id,
        correct_word=word.word,
        definition_options=options,
    )


def _evaluate_task(answer: str, task: Task) -> bool:
    answer = answer.strip().lower()
    if not answer:
        return False
    if task.task_type == "fill_gap":
        return answer == task.correct_word.lower()
    if task.task_type == "which_definition":
        try:
            return int(answer) == task.word_id
        except ValueError:
            return False
    return False


# ── Session state ─────────────────────────────────────────────────────────────

@dataclass
class PackProgress:
    pack_id: int
    preset_name: str
    actions: dict[str, float]
    remaining: deque[int]
    pack_name: str = ""
    learned: set[int] = field(default_factory=set)
    word_info: dict[int, WordInfo] = field(default_factory=dict)
    current: int | None = None
    current_task: Task | None = None

    @classmethod
    def from_pack(cls, pack: Pack, preset: Preset) -> "PackProgress":
        progress = cls(
            pack_id=pack.pack_id,
            preset_name=preset.preset_name,
            actions=dict(preset.actions),
            remaining=deque(),
            pack_name=pack.pack_name,
            word_info=dict(),
        )
        for wid in pack.word_ids:
            progress.add_new_word(wid)
        return progress

    def peek_current(self) -> int | None:
        if self.current is None and self.remaining:
            self.current = self.remaining[0]
        return self.current

    def _pop_and_advance(self, delta: float, action: str) -> ActionResult:
        word_id = self.remaining.popleft()
        if word_id in self.word_info:
            self.word_info[word_id].update(delta)
            info = self.word_info[word_id]
            removed = info.need_to_remove()
            new_fam: float | None = info.familiarity
        else:
            removed = True
            new_fam = None
        if removed:
            self.learned.add(word_id)
        else:
            self.remaining.append(word_id)
        self.current = None
        self.current_task = None
        return ActionResult(
            word_id=word_id, action=action, delta=delta,
            new_familiarity=new_fam, removed=removed,
        )

    def apply_action(self, action: str) -> ActionResult | None:
        if not self.remaining or action not in self.actions:
            return None
        return self._pop_and_advance(self.actions[action], action)

    def apply_task_response(self, answer: str) -> TaskResult | None:
        if self.current_task is None or not self.remaining:
            return None
        task = self.current_task
        correct = _evaluate_task(answer, task)
        if task.task_type == "which_definition":
            delta_key = "which_definition"
        elif task.task_type == "fill_gap" and task.answer_mode == "choice":
            delta_key = "fill_gap_choice"
        elif task.task_type == "fill_gap" and task.answer_mode == "text":
            delta_key = "fill_gap_text"
        else:
            delta_key = "which_definition"

        delta = TASK_DELTAS[delta_key]["correct" if correct else "wrong"]
        result = self._pop_and_advance(delta, "task_correct" if correct else "task_wrong")
        return TaskResult(
            correct=correct,
            correct_word=task.correct_word,
            task_type=task.task_type,
            delta=result.delta,
            removed=result.removed,
        )

    def generate_task(self, word: Any, other_words: list, chunk: str | None) -> Task:
        info = self.word_info.get(word.word_id)
        is_first_show = info is None or info.shows == 0
        task = _generate_task(word, other_words, chunk, self.actions, is_first_show)
        self.current_task = task
        return task

    def add_new_word(self, word_id: int) -> None:
        self.remaining.append(word_id)
        self.word_info.setdefault(word_id, WordInfo(0, 0.0))

    def is_complete(self) -> bool:
        return len(self.remaining) == 0

    def current_familiarity(self) -> float:
        if self.current is None or self.current not in self.word_info:
            return 0.0
        return self.word_info[self.current].familiarity


@dataclass
class SessionState:
    created_at: datetime
    active_pack: PackProgress | None = None
    progress_by_pack: dict[int, PackProgress] = field(default_factory=dict)

    @classmethod
    def new(cls) -> "SessionState":
        return cls(created_at=datetime.now(timezone.utc))

    def start_pack(self, pack: Pack, preset: Preset) -> tuple[PackProgress, bool]:
        """Returns (progress, was_reset). Resets if completed or preset changed."""
        progress = self.progress_by_pack.get(pack.pack_id)
        was_reset = False
        if (
            progress is None
            or progress.is_complete()
            or progress.preset_name != preset.preset_name
        ):
            progress = PackProgress.from_pack(pack, preset)
            self.progress_by_pack[pack.pack_id] = progress
            was_reset = True
        self.active_pack = progress
        return progress, was_reset

    def clear_active(self) -> None:
        self.active_pack = None


sessions: dict[str, SessionState] = {}


def get_or_create(sid: str) -> tuple[SessionState, bool]:
    """Return (state, created). created=True when a fresh session was made."""
    state = sessions.get(sid)
    if state is None:
        state = SessionState.new()
        sessions[sid] = state
        return state, True
    return state, False
