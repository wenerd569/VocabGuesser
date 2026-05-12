import uuid
from pydantic_ai import Agent
from ..models import Exercise, ExerciseType

GENERATOR_INSTRUCTION = """
Generate a B2-level ERROR CORRECTION exercise.

Pick one common B2 grammar mistake from these categories (rotate):
- wrong tense (e.g., "I'm living here since 2020")
- wrong conditional form (e.g., "If I would have known...")
- article misuse (a/an/the/zero)
- subject-verb agreement
- preposition misuse
- gerund vs infinitive confusion
- word order

Build the exercise:
- instruction: "Find and correct the grammatical error in this sentence."
- prompt: ONE sentence containing exactly ONE clear error.
- expected_answer: the same sentence, fully corrected.
- grammar_topic: specific name of the rule violated.

The expected_answer MUST be grammatically correct (verify with check_grammar tool).
The prompt SHOULD contain a real error (do NOT call check_grammar on the prompt).
"""


def generate(agent: Agent) -> Exercise:
    result = agent.run_sync(GENERATOR_INSTRUCTION)
    ex = result.output
    ex.id = str(uuid.uuid4())
    ex.exercise_type = ExerciseType.ERROR_CORRECTION
    return ex
