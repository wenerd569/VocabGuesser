import uuid
from pydantic_ai import Agent
from ..models import Exercise, ExerciseType

GENERATOR_INSTRUCTION = """
Generate a B2-level PHRASAL VERBS exercise.

Build the exercise:
- instruction: "Replace the word(s) in bold with an appropriate phrasal verb in the correct form."
- prompt: a sentence with one plain verb or phrase in **bold**.
  Example: "The meeting was **cancelled** at the last minute."
- expected_answer: the same sentence with the phrasal verb substituted in.
  Example: "The meeting was called off at the last minute."
- grammar_topic: e.g. "Phrasal verb: call off (= cancel)".
- metadata.accept_alternatives: include common synonyms in phrasal-verb form.

The phrasal verb MUST agree with the original tense/voice.
Verify expected_answer with check_grammar tool before returning.
"""


def generate(agent: Agent) -> Exercise:
    result = agent.run_sync(GENERATOR_INSTRUCTION)
    ex = result.output
    ex.id = str(uuid.uuid4())
    ex.exercise_type = ExerciseType.PHRASAL_VERBS
    return ex
