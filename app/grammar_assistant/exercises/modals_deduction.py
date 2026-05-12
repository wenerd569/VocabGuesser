import uuid
from pydantic_ai import Agent
from ..models import Exercise, ExerciseType

GENERATOR_INSTRUCTION = """
Generate a B2-level MODAL VERBS OF DEDUCTION exercise (past form).

Test: must have / can't have / might have / could have / should have / needn't have + V3.

Build the exercise:
- instruction: "Express the speaker's degree of certainty about the past using a modal verb."
- prompt: a short situation + a hint about certainty.
  Example: "The grass is wet. (You are 90% sure it rained.)"
- expected_answer: a sentence using the appropriate modal perfect.
  Example: "It must have rained."
- grammar_topic: e.g. "Modal of Deduction: must have (strong past certainty)".
- metadata.accept_alternatives: include reasonable phrasings.

Verify expected_answer with check_grammar tool before returning.
"""


def generate(agent: Agent) -> Exercise:
    result = agent.run_sync(GENERATOR_INSTRUCTION)
    ex = result.output
    ex.id = str(uuid.uuid4())
    ex.exercise_type = ExerciseType.MODAL_DEDUCTION
    return ex
