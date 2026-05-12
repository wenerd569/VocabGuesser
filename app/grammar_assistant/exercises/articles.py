import uuid
from pydantic_ai import Agent
from ..models import Exercise, ExerciseType

GENERATOR_INSTRUCTION = """
Generate a B2-level ARTICLES exercise (a / an / the / zero article).

Cover B2-level patterns:
- zero article with abstract nouns, meals, languages
- "the" with unique nouns, superlatives, oceans, mountain ranges
- "the" + nationality adjective for groups
- a/an with countable singular nouns first mention
- geographical names rules (countries, rivers, deserts)

Build the exercise:
- instruction: "Fill in the gaps with a, an, the, or — (no article)."
- prompt: a sentence with several gaps marked as "___".
- expected_answer: the full sentence with all gaps correctly filled.
- grammar_topic: e.g. "Articles with unique nouns and meals".

Verify expected_answer with check_grammar tool before returning.
"""


def generate(agent: Agent) -> Exercise:
    result = agent.run_sync(GENERATOR_INSTRUCTION)
    ex = result.output
    ex.id = str(uuid.uuid4())
    ex.exercise_type = ExerciseType.ARTICLES
    return ex
