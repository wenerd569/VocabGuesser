import language_tool_python
from ..config import config
from ..models import GrammarError

_tool = None


def _get_tool():
    global _tool
    if _tool is None:
        _tool = language_tool_python.LanguageTool(config.language_tool_locale)
    return _tool


def check_grammar(text: str) -> list[GrammarError]:
    tool = _get_tool()
    matches = tool.check(text)
    return [
        GrammarError(
            message=m.message,
            category=m.category,
            offset=m.offset,
            length=getattr(m, 'errorLength', None) or getattr(m, 'matchedLength', 0),
            suggested_replacements=m.replacements[:5],
        )
        for m in matches
    ]


def close_tool():
    global _tool
    if _tool is not None:
        _tool.close()
        _tool = None
