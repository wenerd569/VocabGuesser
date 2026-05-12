import uuid
from typing import Optional
from .models import ExerciseType, Exercise, ValidationResult
from .exercises.registry import EXERCISE_REGISTRY, pick_random_type, get_enabled_types
from .agents.generator import generator_agent
from .agents.validator import validator_agent
from .logging_events import (
    log_exercise_generated, log_exercise_answered,
    log_exercise_fallback, log_assistant_error,
)
from .fallback_bank.exercises import get_fallback
from .config import config


def generate_exercise(
    exercise_type: Optional[ExerciseType] = None,
    user_id: Optional[str] = None,
) -> Exercise:
    target_type = exercise_type or pick_random_type()
    cfg = EXERCISE_REGISTRY[target_type]

    for attempt in range(config.max_regeneration_attempts):
        try:
            exercise = cfg.generator_fn(generator_agent)
            log_exercise_generated(exercise, regeneration_count=attempt, user_id=user_id)
            return exercise
        except Exception as e:
            log_assistant_error("generator", type(e).__name__)
            continue

    exercise = get_fallback(target_type)
    log_exercise_fallback(target_type, reason="max_regenerations_exceeded", user_id=user_id)
    log_exercise_generated(
        exercise,
        regeneration_count=config.max_regeneration_attempts,
        user_id=user_id,
    )
    return exercise


def validate_answer(
    exercise: Exercise,
    user_answer: str,
    user_id: Optional[str] = None,
) -> ValidationResult:
    if not user_answer or len(user_answer) > 500:
        raise ValueError("user_answer must be between 1 and 500 characters")

    prompt = f"""
Exercise type: {exercise.exercise_type.value}
Grammar topic: {exercise.grammar_topic}
Instruction: {exercise.instruction}
Prompt: {exercise.prompt}
Expected answer: {exercise.expected_answer}
Accept alternatives: {exercise.metadata.get('accept_alternatives', [])}

User's answer: {user_answer}

Validate the user's answer using your tools. Follow the workflow strictly.
""".strip()

    try:
        result = validator_agent.run_sync(prompt)
        validation = result.output
        validation.exercise_id = exercise.id
        validation.user_answer = user_answer
        validation.correct_answer = exercise.expected_answer
        log_exercise_answered(exercise, validation, user_id=user_id)
        return validation
    except Exception as e:
        log_assistant_error("validator", type(e).__name__, exercise_id=exercise.id)
        raise


def submit_custom_exercise(
    user_sentence: str,
    exercise_type: ExerciseType,
    user_id: Optional[str] = None,
) -> Exercise:
    prompt = (
        f"Use this sentence as the basis for the exercise: '{user_sentence}'. "
        f"Build a {exercise_type.value} exercise around it. "
        f"Do NOT check the user's input sentence for errors — accept it as given."
    )
    result = generator_agent.run_sync(prompt)
    exercise = result.output
    exercise.exercise_type = exercise_type
    exercise.id = str(uuid.uuid4())
    log_exercise_generated(exercise, regeneration_count=0, user_id=user_id, is_custom=True)
    return exercise


__all__ = [
    "ExerciseType", "Exercise", "ValidationResult",
    "generate_exercise", "validate_answer", "submit_custom_exercise",
    "get_enabled_types",
]
