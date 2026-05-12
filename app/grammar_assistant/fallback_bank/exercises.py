import random
import uuid
from ..models import Exercise, ExerciseType


_FALLBACK: dict[ExerciseType, list[Exercise]] = {
    ExerciseType.ERROR_CORRECTION: [
        Exercise(
            id="", exercise_type=ExerciseType.ERROR_CORRECTION,
            instruction="Find and correct the grammatical error in this sentence.",
            prompt="I'm living in this city since 2020.",
            expected_answer="I have been living in this city since 2020.",
            grammar_topic="Present Perfect Continuous with 'since'",
            metadata={"accept_alternatives": ["I've been living in this city since 2020."]},
        ),
    ],
    ExerciseType.CONDITIONAL: [
        Exercise(
            id="", exercise_type=ExerciseType.CONDITIONAL,
            instruction="Combine these two facts using a Third Conditional.",
            prompt="I didn't study. I failed the exam.",
            expected_answer="If I had studied, I wouldn't have failed the exam.",
            grammar_topic="Third Conditional",
            metadata={"accept_alternatives": [
                "If I had studied, I would not have failed the exam.",
            ]},
        ),
    ],
    ExerciseType.TENSE_TRANSFORMATION: [
        Exercise(
            id="", exercise_type=ExerciseType.TENSE_TRANSFORMATION,
            instruction="Rewrite this sentence in the Present Perfect Continuous, emphasizing duration since morning.",
            prompt="I am writing a report.",
            expected_answer="I have been writing a report since morning.",
            grammar_topic="Present Continuous → Present Perfect Continuous",
            metadata={"accept_alternatives": ["I've been writing a report since morning."]},
        ),
    ],
    ExerciseType.GERUND_INFINITIVE: [
        Exercise(
            id="", exercise_type=ExerciseType.GERUND_INFINITIVE,
            instruction="Put the verb in brackets in the correct form (gerund or infinitive).",
            prompt="I remember (lock) the door, but now I'm not sure.",
            expected_answer="I remember locking the door, but now I'm not sure.",
            grammar_topic="remember + gerund (recall past action)",
            metadata={},
        ),
    ],
    ExerciseType.REPORTED_SPEECH: [
        Exercise(
            id="", exercise_type=ExerciseType.REPORTED_SPEECH,
            instruction="Report what the speaker said.",
            prompt='She said: "I will have finished it by Monday."',
            expected_answer="She said that she would have finished it by Monday.",
            grammar_topic="Backshift: will have → would have",
            metadata={"accept_alternatives": [
                "She said she would have finished it by Monday.",
                "She said that she'd have finished it by Monday.",
            ]},
        ),
    ],
    ExerciseType.MODAL_DEDUCTION: [
        Exercise(
            id="", exercise_type=ExerciseType.MODAL_DEDUCTION,
            instruction="Express the speaker's degree of certainty about the past using a modal verb. The speaker is 90% sure it rained.",
            prompt="The grass is wet.",
            expected_answer="It must have rained.",
            grammar_topic="Modal of Deduction: must have (strong past certainty)",
            metadata={},
        ),
    ],
    ExerciseType.ARTICLES: [
        Exercise(
            id="", exercise_type=ExerciseType.ARTICLES,
            instruction="Fill in the gaps with a, an, the, or — (no article).",
            prompt="___ Sun rises in ___ east. I had ___ breakfast at ___ hotel where I was staying.",
            expected_answer="The Sun rises in the east. I had — breakfast at the hotel where I was staying.",
            grammar_topic="Articles with unique nouns and meals",
            metadata={},
        ),
    ],
    ExerciseType.INVERSION: [
        Exercise(
            id="", exercise_type=ExerciseType.INVERSION,
            instruction="Rewrite this sentence starting with the word in brackets. Use inversion.",
            prompt="I have never seen such a beautiful sunset. (Never)",
            expected_answer="Never have I seen such a beautiful sunset.",
            grammar_topic="Inversion after 'Never' with Present Perfect",
            metadata={},
        ),
    ],
    ExerciseType.PASSIVE_VOICE: [
        Exercise(
            id="", exercise_type=ExerciseType.PASSIVE_VOICE,
            instruction="Rewrite this sentence in the passive voice.",
            prompt="They have built a new bridge over the river.",
            expected_answer="A new bridge has been built over the river.",
            grammar_topic="Present Perfect Passive",
            metadata={"accept_alternatives": [
                "A new bridge has been built over the river by them.",
            ]},
        ),
    ],
    ExerciseType.PREPOSITIONS: [
        Exercise(
            id="", exercise_type=ExerciseType.PREPOSITIONS,
            instruction="Fill in the gaps with the correct prepositions.",
            prompt="She's been married ___ him ___ 10 years.",
            expected_answer="She's been married to him for 10 years.",
            grammar_topic="Dependent preposition 'married to' + 'for' with duration",
            metadata={},
        ),
    ],
    ExerciseType.SENTENCE_COMBINING: [
        Exercise(
            id="", exercise_type=ExerciseType.SENTENCE_COMBINING,
            instruction='Combine these two sentences using "despite".',
            prompt="He was tired. He kept working.",
            expected_answer="Despite being tired, he kept working.",
            grammar_topic="Despite + gerund clause",
            metadata={"accept_alternatives": [
                "Despite the fact that he was tired, he kept working.",
                "He kept working despite being tired.",
            ]},
        ),
    ],
    ExerciseType.PHRASAL_VERBS: [
        Exercise(
            id="", exercise_type=ExerciseType.PHRASAL_VERBS,
            instruction="Replace the word in bold with an appropriate phrasal verb in the correct form.",
            prompt="The meeting was **cancelled** at the last minute.",
            expected_answer="The meeting was called off at the last minute.",
            grammar_topic="Phrasal verb: call off (= cancel)",
            metadata={"accept_alternatives": [
                "The meeting was put off at the last minute.",
            ]},
        ),
    ],
}


def get_fallback(exercise_type: ExerciseType) -> Exercise:
    pool = _FALLBACK.get(exercise_type, [])
    if not pool:
        raise RuntimeError(f"No fallback exercises for {exercise_type}")
    chosen = random.choice(pool)
    new_exercise = chosen.model_copy(deep=True)
    new_exercise.id = str(uuid.uuid4())
    return new_exercise
