import spacy
from ..config import config
from ..models import SentenceAnalysis, TokenInfo

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load(config.spacy_model)
    return _nlp


def analyze_sentence(text: str) -> SentenceAnalysis:
    nlp = _get_nlp()
    doc = nlp(text)
    tokens_info = [
        TokenInfo(
            text=t.text, pos=t.pos_, tag=t.tag_,
            dep=t.dep_, lemma=t.lemma_, morph=str(t.morph),
        )
        for t in doc
    ]
    return SentenceAnalysis(
        tokens=tokens_info,
        detected_tenses=detect_verb_tenses(doc),
        has_inversion=detect_inversion(doc),
        has_passive=detect_passive(doc),
    )


def detect_verb_tenses(doc) -> list[str]:
    found = []
    for token in doc:
        if token.pos_ not in ("VERB", "AUX"):
            continue
        if token.dep_ in ("aux", "auxpass"):
            continue

        aux_children = [c for c in token.children if c.dep_ in ("aux", "auxpass")]
        aux_lemmas = [c.lemma_.lower() for c in aux_children]
        aux_tags = [c.tag_ for c in aux_children]
        main_tag = token.tag_

        if (("will" in aux_lemmas or "shall" in aux_lemmas)
                and "have" in aux_lemmas and "be" in aux_lemmas and main_tag == "VBG"):
            found.append("Future Perfect Continuous"); continue
        if (("will" in aux_lemmas or "shall" in aux_lemmas)
                and "have" in aux_lemmas and main_tag == "VBN"):
            found.append("Future Perfect"); continue
        if (("will" in aux_lemmas or "shall" in aux_lemmas)
                and "be" in aux_lemmas and main_tag == "VBG"):
            found.append("Future Continuous"); continue
        if ("will" in aux_lemmas or "shall" in aux_lemmas) and main_tag == "VB":
            found.append("Future Simple"); continue
        if "have" in aux_lemmas and "VBD" in aux_tags and "be" in aux_lemmas and main_tag == "VBG":
            found.append("Past Perfect Continuous"); continue
        if "have" in aux_lemmas and "VBD" in aux_tags and main_tag == "VBN":
            found.append("Past Perfect"); continue
        if ("have" in aux_lemmas and ("VBZ" in aux_tags or "VBP" in aux_tags)
                and "be" in aux_lemmas and main_tag == "VBG"):
            found.append("Present Perfect Continuous"); continue
        if "have" in aux_lemmas and ("VBZ" in aux_tags or "VBP" in aux_tags) and main_tag == "VBN":
            found.append("Present Perfect"); continue
        if "be" in aux_lemmas and "VBD" in aux_tags and main_tag == "VBG":
            found.append("Past Continuous"); continue
        if "be" in aux_lemmas and ("VBZ" in aux_tags or "VBP" in aux_tags) and main_tag == "VBG":
            found.append("Present Continuous"); continue

        modal_lemmas = {"can", "could", "may", "might", "must", "shall",
                        "should", "will", "would", "ought", "need"}
        modals_in_aux = [l for l in aux_lemmas if l in modal_lemmas]
        if modals_in_aux and "have" in aux_lemmas and main_tag == "VBN":
            found.append(f"Modal Perfect ({modals_in_aux[0]} have V3)"); continue
        if modals_in_aux and main_tag == "VB":
            found.append(f"Modal ({modals_in_aux[0]})"); continue
        if main_tag == "VBD":
            found.append("Past Simple"); continue
        if main_tag in ("VBZ", "VBP", "VB"):
            found.append("Present Simple"); continue

    return found


def detect_inversion(doc) -> bool:
    if len(doc) < 2:
        return False
    inversion_starters = {
        "never", "rarely", "seldom", "hardly", "scarcely", "barely",
        "no", "not", "only", "little", "nowhere", "neither", "nor",
    }
    if doc[0].text.lower() not in inversion_starters:
        return False
    for t in doc[:6]:
        if t.dep_ in ("aux", "auxpass"):
            for child in t.head.children:
                if child.dep_ == "nsubj" and child.i > t.i:
                    return True
    return False


def detect_passive(doc) -> bool:
    return any(t.dep_ == "auxpass" for t in doc)
