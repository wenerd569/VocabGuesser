import uuid
from pydantic_ai import Agent
from ..models import Exercise, ExerciseType

GENERATOR_INSTRUCTION = """
Generate a B2-level TENSE TRANSFORMATION exercise.

Pick a source sentence in one tense, then ask the learner to rewrite it in a
target tense WHILE PRESERVING MEANING (with appropriate time markers if needed).

Suggested pairs (rotate):
- Present Simple ↔ Present Perfect
- Present Continuous → Present Perfect Continuous (with "since" / "for")
- Past Simple → Past Perfect (with another past event)
- Past Simple → Used to / Would (for habits)
- Present Simple → Future Simple / Future Continuous

Build the exercise:
- instruction: "Rewrite this sentence in <TARGET TENSE>. <Optional context>."
- prompt: ONE source sentence.
- expected_answer: the rewritten sentence.
- grammar_topic: e.g. "Present Continuous → Present Perfect Continuous".

Verify expected_answer with check_grammar tool before returning.
"""


def generate(agent: Agent) -> Exercise:
    result = agent.run_sync(GENERATOR_INSTRUCTION)
    ex = result.output
    ex.id = str(uuid.uuid4())
    ex.exercise_type = ExerciseType.TENSE_TRANSFORMATION
    return ex
