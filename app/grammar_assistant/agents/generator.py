import os
from pathlib import Path
from pydantic_ai import Agent
from pydantic_ai.models.groq import GroqModel
from ..config import config
from ..models import Exercise, GrammarError
from ..tools.language_tool import check_grammar

os.environ.setdefault("GROQ_API_KEY", config.groq_api_key)

_SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "generator_system.md").read_text(encoding="utf-8")

model = GroqModel(config.llm_model)

generator_agent = Agent(
    model=model,
    output_type=Exercise,
    system_prompt=_SYSTEM_PROMPT,
    retries=2,
)


@generator_agent.tool_plain
def check_grammar_tool(text: str) -> list[GrammarError]:
    """Check English text for grammar, spelling, and style errors. Call on expected_answer before returning."""
    return check_grammar(text)
