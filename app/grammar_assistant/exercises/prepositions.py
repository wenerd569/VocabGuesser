import uuid
from pydantic_ai import Agent
from ..models import Exercise, ExerciseType

GENERATOR_INSTRUCTION = """
Generate a B2-level PREPOSITIONS exercise.

Cover B2 trouble spots:
- dependent prepositions after verbs (interested in, depend on, agree with/on)
- dependent prepositions after adjectives (good at, afraid of, similar to)
- dependent prepositions after nouns (reason for, increase in, effect on)
- time and place prepositions (in/on/at)
- "for" vs "since" with Present Perfect
- "by" vs "until"

Build the exercise:
- instruction: "Fill in the gaps with the correct prepositions."
- prompt: a sentence with 2-3 gaps marked as "___".
- expected_answer: full sentence with the correct prepositions filled in.
- grammar_topic: e.g. "Dependent prepositions: married to, for + duration".

Verify expected_answer with check_grammar tool before returning.
"""


def generate(agent: Agent) -> Exercise:
    result = agent.run_sync(GENERATOR_INSTRUCTION)
    ex = result.output
    ex.id = str(uuid.uuid4())
    ex.exercise_type = ExerciseType.PREPOSITIONS
    return ex
