from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ExerciseType(str, Enum):
    ERROR_CORRECTION = "error_correction"
    CONDITIONAL = "conditional"
    TENSE_TRANSFORMATION = "tense_transformation"
    GERUND_INFINITIVE = "gerund_infinitive"
    REPORTED_SPEECH = "reported_speech"
    MODAL_DEDUCTION = "modal_deduction"
    ARTICLES = "articles"
    INVERSION = "inversion"
    PASSIVE_VOICE = "passive_voice"
    PREPOSITIONS = "prepositions"
    SENTENCE_COMBINING = "sentence_combining"
    PHRASAL_VERBS = "phrasal_verbs"


class Exercise(BaseModel):
    id: str = ""
    exercise_type: ExerciseType
    instruction: str
    prompt: str
    expected_answer: str
    grammar_topic: str
    metadata: dict = Field(default_factory=dict)


class GrammarError(BaseModel):
    message: str
    category: str
    offset: int
    length: int
    suggested_replacements: list[str] = Field(default_factory=list)


class TokenInfo(BaseModel):
    text: str
    pos: str
    tag: str
    dep: str
    lemma: str
    morph: str


class SentenceAnalysis(BaseModel):
    tokens: list[TokenInfo]
    detected_tenses: list[str]
    has_inversion: bool
    has_passive: bool


class StructureDiff(BaseModel):
    tense_changed: bool
    tenses_before: list[str]
    tenses_after: list[str]
    inversion_changed: bool
    passive_changed: bool


class ValidationResult(BaseModel):
    exercise_id: str = ""
    is_correct: bool
    user_answer: str = ""
    correct_answer: str = ""
    rule_name: str
    explanation: str
    what_to_review: str = ""
    grammar_errors: list[GrammarError] = Field(default_factory=list)
    matched_alternative: Optional[str] = None
