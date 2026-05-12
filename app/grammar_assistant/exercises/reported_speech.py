import uuid
from pydantic_ai import Agent
from ..models import Exercise, ExerciseType

GENERATOR_INSTRUCTION = """
Generate a B2-level REPORTED SPEECH exercise.

Test backshift rules. Include a variety:
- Present Simple → Past Simple
- Present Continuous → Past Continuous
- Present Perfect → Past Perfect
- will → would / can → could / must → had to
- this/here/now/today → that/there/then/that day

Also rotate sentence types: statements, yes/no questions, wh-questions, commands.

Build the exercise:
- instruction: "Report what the speaker said."
- prompt: direct speech with reporting verb tag.
- expected_answer: the reported speech version.
- grammar_topic: e.g. "Backshift: will → would".
- metadata.accept_alternatives: include with/without "that", contracted forms.

Verify expected_answer with check_grammar tool before returning.
"""


def generate(agent: Agent) -> Exercise:
    result = agent.run_sync(GENERATOR_INSTRUCTION)
    ex = result.output
    ex.id = str(uuid.uuid4())
    ex.exercise_type = ExerciseType.REPORTED_SPEECH
    return ex
