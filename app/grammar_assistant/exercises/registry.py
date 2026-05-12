import random
from ..models import ExerciseType
from .base import ExerciseConfig
from . import (
    error_correction, conditionals, tense_transformation,
    gerund_infinitive, reported_speech, modals_deduction,
    articles, word_order_inversion, passive_voice,
    prepositions, sentence_combining, phrasal_verbs,
)


EXERCISE_REGISTRY: dict[ExerciseType, ExerciseConfig] = {
    ExerciseType.ERROR_CORRECTION: ExerciseConfig(
        enabled=True, weight=2.0, difficulty="B2",
        generator_fn=error_correction.generate,
        validator_hints={"primary_tool": "check_grammar"},
        fallback_bank_key="error_correction",
    ),
    ExerciseType.CONDITIONAL: ExerciseConfig(
        enabled=True, weight=1.5, difficulty="B2",
        generator_fn=conditionals.generate,
        validator_hints={"primary_tool": "compare_structures"},
        fallback_bank_key="conditional",
    ),
    ExerciseType.TENSE_TRANSFORMATION: ExerciseConfig(
        enabled=True, weight=1.5, difficulty="B2",
        generator_fn=tense_transformation.generate,
        validator_hints={"primary_tool": "compare_structures"},
        fallback_bank_key="tense_transformation",
    ),
    ExerciseType.GERUND_INFINITIVE: ExerciseConfig(
        enabled=True, weight=1.0, difficulty="B2",
        generator_fn=gerund_infinitive.generate,
        validator_hints={"primary_tool": "check_grammar"},
        fallback_bank_key="gerund_infinitive",
    ),
    ExerciseType.REPORTED_SPEECH: ExerciseConfig(
        enabled=True, weight=1.0, difficulty="B2",
        generator_fn=reported_speech.generate,
        validator_hints={"primary_tool": "compare_structures"},
        fallback_bank_key="reported_speech",
    ),
    ExerciseType.MODAL_DEDUCTION: ExerciseConfig(
        enabled=True, weight=1.0, difficulty="B2",
        generator_fn=modals_deduction.generate,
        validator_hints={"primary_tool": "check_grammar"},
        fallback_bank_key="modal_deduction",
    ),
    ExerciseType.ARTICLES: ExerciseConfig(
        enabled=True, weight=1.0, difficulty="B2",
        generator_fn=articles.generate,
        validator_hints={"primary_tool": "check_grammar"},
        fallback_bank_key="articles",
    ),
    ExerciseType.INVERSION: ExerciseConfig(
        enabled=True, weight=0.7, difficulty="B2",
        generator_fn=word_order_inversion.generate,
        validator_hints={"primary_tool": "analyze_sentence"},
        fallback_bank_key="inversion",
    ),
    ExerciseType.PASSIVE_VOICE: ExerciseConfig(
        enabled=True, weight=1.0, difficulty="B2",
        generator_fn=passive_voice.generate,
        validator_hints={"primary_tool": "compare_structures"},
        fallback_bank_key="passive_voice",
    ),
    ExerciseType.PREPOSITIONS: ExerciseConfig(
        enabled=True, weight=1.0, difficulty="B2",
        generator_fn=prepositions.generate,
        validator_hints={"primary_tool": "check_grammar"},
        fallback_bank_key="prepositions",
    ),
    ExerciseType.SENTENCE_COMBINING: ExerciseConfig(
        enabled=True, weight=1.0, difficulty="B2",
        generator_fn=sentence_combining.generate,
        validator_hints={"primary_tool": "check_grammar"},
        fallback_bank_key="sentence_combining",
    ),
    ExerciseType.PHRASAL_VERBS: ExerciseConfig(
        enabled=True, weight=0.8, difficulty="B2",
        generator_fn=phrasal_verbs.generate,
        validator_hints={"primary_tool": "check_grammar"},
        fallback_bank_key="phrasal_verbs",
    ),
}


def get_enabled_types() -> list[ExerciseType]:
    return [t for t, cfg in EXERCISE_REGISTRY.items() if cfg.enabled]


def pick_random_type() -> ExerciseType:
    enabled = [(t, cfg.weight) for t, cfg in EXERCISE_REGISTRY.items() if cfg.enabled]
    if not enabled:
        raise RuntimeError("No enabled exercise types")
    types, weights = zip(*enabled)
    return random.choices(types, weights=weights, k=1)[0]
