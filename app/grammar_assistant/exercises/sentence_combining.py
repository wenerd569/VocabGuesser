import uuid
from pydantic_ai import Agent
from ..models import Exercise, ExerciseType

GENERATOR_INSTRUCTION = """
Generate a B2-level SENTENCE COMBINING exercise.

Test joining two simple sentences using one of these constructions:
- despite / in spite of (+ noun/gerund/the fact that)
- although / even though / though
- because of / due to / owing to
- relative clauses (defining and non-defining): who, which, that, whose, where
- participle clauses: "Walking down the street, ...", "Built in 1820, ..."
- so / such ... that
- too ... to / enough ... to

Build the exercise:
- instruction: clearly say which construction to use.
- prompt: two short simple sentences.
- expected_answer: the combined sentence.
- grammar_topic: e.g. "Despite + gerund clause".
- metadata.accept_alternatives: include reasonable variants.

Verify expected_answer with check_grammar tool before returning.
"""


def generate(agent: Agent) -> Exercise:
    result = agent.run_sync(GENERATOR_INSTRUCTION)
    ex = result.output
    ex.id = str(uuid.uuid4())
    ex.exercise_type = ExerciseType.SENTENCE_COMBINING
    return ex
