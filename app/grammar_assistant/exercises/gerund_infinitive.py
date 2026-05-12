import uuid
from pydantic_ai import Agent
from ..models import Exercise, ExerciseType

GENERATOR_INSTRUCTION = """
Generate a B2-level GERUND vs INFINITIVE exercise.

Focus on verbs where meaning changes with gerund vs infinitive:
- remember doing / remember to do
- forget doing / forget to do
- stop doing / stop to do
- regret doing / regret to do
- try doing / try to do
- mean doing / mean to do
- go on doing / go on to do

Or verbs strictly followed by one form:
- enjoy / avoid / suggest / consider → gerund
- decide / agree / promise / refuse → infinitive

Build the exercise:
- instruction: "Put the verb in brackets in the correct form (gerund or infinitive)."
- prompt: a sentence with one verb in brackets in base form.
- expected_answer: the full sentence with the verb in the correct form.
- grammar_topic: e.g. "remember + gerund (recall past action)".

Verify expected_answer with check_grammar tool before returning.
"""


def generate(agent: Agent) -> Exercise:
    result = agent.run_sync(GENERATOR_INSTRUCTION)
    ex = result.output
    ex.id = str(uuid.uuid4())
    ex.exercise_type = ExerciseType.GERUND_INFINITIVE
    return ex
