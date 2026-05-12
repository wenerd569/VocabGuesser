import uuid
from pydantic_ai import Agent
from ..models import Exercise, ExerciseType

GENERATOR_INSTRUCTION = """
Generate a B2-level CONDITIONALS exercise.

Pick ONE type randomly: Zero, First, Second, Third, or Mixed Conditional.
For Mixed prefer: past condition → present result.

Build the exercise:
- instruction: clearly state which conditional to use.
  Example: "Combine these two facts using a Third Conditional."
- prompt: two short factual statements describing a real or hypothetical situation.
  Example: "I didn't study. I failed the exam."
- expected_answer: the resulting conditional sentence.
  Example: "If I had studied, I wouldn't have failed the exam."
- grammar_topic: e.g. "Third Conditional", "Mixed Conditional (past → present)".
- metadata.accept_alternatives: include common valid variants (e.g., contracted/expanded forms).

Verify expected_answer with check_grammar tool before returning.
"""


def generate(agent: Agent) -> Exercise:
    result = agent.run_sync(GENERATOR_INSTRUCTION)
    ex = result.output
    ex.id = str(uuid.uuid4())
    ex.exercise_type = ExerciseType.CONDITIONAL
    return ex
