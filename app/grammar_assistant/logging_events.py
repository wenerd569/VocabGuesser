from typing import Optional
from .models import Exercise, ExerciseType, ValidationResult
from ..logging_mod import write_raw_logs


def log_exercise_generated(
    exercise: Exercise,
    regeneration_count: int,
    user_id: Optional[str] = None,
    is_custom: bool = False,
) -> None:
    write_raw_logs({
        "event": "exercise_generated",
        "exercise_id": exercise.id,
        "exercise_type": exercise.exercise_type.value,
        "grammar_topic": exercise.grammar_topic,
        "regeneration_count": regeneration_count,
        "user_id": user_id,
        "is_custom": is_custom,
    })


def log_exercise_answered(
    exercise: Exercise,
    result: ValidationResult,
    user_id: Optional[str] = None,
) -> None:
    write_raw_logs({
        "event": "exercise_answered",
        "exercise_id": exercise.id,
        "exercise_type": exercise.exercise_type.value,
        "grammar_topic": exercise.grammar_topic,
        "is_correct": result.is_correct,
        "user_answer": result.user_answer,
        "expected_answer": result.correct_answer,
        "rule_name": result.rule_name,
        "grammar_error_categories": [e.category for e in result.grammar_errors],
        "user_id": user_id,
    })


def log_exercise_fallback(
    exercise_type: ExerciseType,
    reason: str,
    user_id: Optional[str] = None,
) -> None:
    write_raw_logs({
        "event": "exercise_fallback",
        "exercise_type": exercise_type.value,
        "reason": reason,
        "user_id": user_id,
    })


def log_assistant_error(
    where: str,
    error_type: str,
    exercise_id: Optional[str] = None,
) -> None:
    write_raw_logs({
        "event": "assistant_error",
        "where": where,
        "error_type": error_type,
        "exercise_id": exercise_id,
    })
