import pandas as pd


    
def word_memorize_metric(session_log: pd.DataFrame) -> pd.Series:
    task_response_log = session_log[session_log["event"] == "task_response"]
    if task_response_log.empty:
        return 0.0

    good_count = 0
    log_by_word = task_response_log.groupby("correct_word")
    total_words = len(log_by_word)
    if total_words == 0:
        return 0.0

    for word_id, group in log_by_word:
        correct = group["correct"].tolist()
        if all(correct):
            continue
        is_recognized = False
        for c in correct:
            if c:
                is_recognized = True
            elif is_recognized and not c:
                is_recognized = False
        if is_recognized:
            good_count += 1

    return good_count / total_words