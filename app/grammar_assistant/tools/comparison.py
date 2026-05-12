from .spacy_tools import analyze_sentence, _get_nlp
from ..models import StructureDiff


def compare_structures(text_a: str, text_b: str) -> StructureDiff:
    a = analyze_sentence(text_a)
    b = analyze_sentence(text_b)
    return StructureDiff(
        tense_changed=sorted(a.detected_tenses) != sorted(b.detected_tenses),
        tenses_before=a.detected_tenses,
        tenses_after=b.detected_tenses,
        inversion_changed=a.has_inversion != b.has_inversion,
        passive_changed=a.has_passive != b.has_passive,
    )


def lemmatize_and_compare(text_a: str, text_b: str) -> bool:
    nlp = _get_nlp()
    lemmas_a = [t.lemma_.lower() for t in nlp(text_a) if not t.is_punct and not t.is_space]
    lemmas_b = [t.lemma_.lower() for t in nlp(text_b) if not t.is_punct and not t.is_space]
    return lemmas_a == lemmas_b
