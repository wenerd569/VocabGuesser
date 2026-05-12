import uuid
from pydantic_ai import Agent
from ..models import Exercise, ExerciseType

GENERATOR_INSTRUCTION = """
Generate a B2/C1-level INVERSION exercise.

Test inversion after negative/restrictive adverbials:
- Never / Rarely / Seldom + have/had + S + V3
- Hardly / Scarcely / Barely + had + S + V3 + when
- No sooner + had + S + V3 + than
- Not only + aux + S + V + but also
- Only after / Only when / Only then + aux + S + V

Build the exercise:
- instruction: "Rewrite this sentence starting with the word in brackets. Use inversion."
- prompt: a normal-order sentence + the starter word in brackets.
  Example: "I have never seen such a beautiful sunset. (Never)"
- expected_answer: the inverted version.
  Example: "Never have I seen such a beautiful sunset."
- grammar_topic: e.g. "Inversion after 'Never' with Present Perfect".

Verify expected_answer with check_grammar tool before returning.
"""


def generate(agent: Agent) -> Exercise:
    result = agent.run_sync(GENERATOR_INSTRUCTION)
    ex = result.output
    ex.id = str(uuid.uuid4())
    ex.exercise_type = ExerciseType.INVERSION
    return ex
