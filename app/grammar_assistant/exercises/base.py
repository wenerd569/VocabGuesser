from dataclasses import dataclass
from typing import Callable
from ..models import Exercise


@dataclass
class ExerciseConfig:
    enabled: bool
    weight: float
    difficulty: str
    generator_fn: Callable[..., Exercise]
    validator_hints: dict
    fallback_bank_key: str
