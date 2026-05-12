import os
from pathlib import Path
from pydantic_ai import Agent
from pydantic_ai.models.groq import GroqModel
from ..config import config
from ..models import (
    ValidationResult, GrammarError, SentenceAnalysis, StructureDiff,
)
from ..tools.language_tool import check_grammar
from ..tools.spacy_tools import analyze_sentence
from ..tools.comparison import compare_structures, lemmatize_and_compare

os.environ.setdefault("GROQ_API_KEY", config.groq_api_key)

_SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "validator_system.md").read_text(encoding="utf-8")

model = GroqModel(config.llm_model)

validator_agent = Agent(
    model=model,
    output_type=ValidationResult,
    system_prompt=_SYSTEM_PROMPT,
    retries=2,
)


@validator_agent.tool_plain
def check_grammar_tool(text: str) -> list[GrammarError]:
    """Check English text for grammar errors. ALWAYS call on user_answer first."""
    return check_grammar(text)


@validator_agent.tool_plain
def analyze_sentence_tool(text: str) -> SentenceAnalysis:
    """Analyze grammatical structure: POS tags, tenses, inversion, passive voice."""
    return analyze_sentence(text)


@validator_agent.tool_plain
def compare_structures_tool(expected: str, user: str) -> StructureDiff:
    """Compare grammatical structures. Use for transformation exercises (tense/voice/reported speech/inversion)."""
    return compare_structures(expected, user)


@validator_agent.tool_plain
def lemmatize_compare_tool(a: str, b: str) -> bool:
    """Compare two sentences by lemmas (ignores casing/punctuation). Returns True if equivalent."""
    return lemmatize_and_compare(a, b)


@validator_agent.output_validator
async def ensure_explanation_quality(result: ValidationResult) -> ValidationResult:
    if not result.rule_name.strip():
        raise ValueError("rule_name must not be empty")
    if not result.explanation.strip():
        raise ValueError("explanation must not be empty")
    if not result.is_correct and not result.what_to_review.strip():
        raise ValueError("what_to_review must be filled when is_correct=False")
    return result
