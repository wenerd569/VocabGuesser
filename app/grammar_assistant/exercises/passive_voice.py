import uuid
from pydantic_ai import Agent
from ..models import Exercise, ExerciseType

GENERATOR_INSTRUCTION = """
Generate a B2-level PASSIVE VOICE exercise.

Cover passive in different tenses:
- Present Simple Passive: is/are + V3
- Past Simple Passive: was/were + V3
- Present Perfect Passive: have/has been + V3
- Past Perfect Passive: had been + V3
- Future Passive: will be + V3
- Modal Passive: must be done / should be done

Build the exercise:
- instruction: "Rewrite this sentence in the passive voice."
- prompt: an active-voice sentence.
- expected_answer: the passive version.
- grammar_topic: e.g. "Present Perfect Passive".
- metadata.accept_alternatives: with/without by-agent.

Verify expected_answer with check_grammar tool before returning.
"""


def generate(agent: Agent) -> Exercise:
    result = agent.run_sync(GENERATOR_INSTRUCTION)
    ex = result.output
    ex.id = str(uuid.uuid4())
    ex.exercise_type = ExerciseType.PASSIVE_VOICE
    return ex
