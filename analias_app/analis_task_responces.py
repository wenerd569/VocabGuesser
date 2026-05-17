import pandas as pd


def word_recognize_metric(logs: pd.DataFrame) -> pd.Series:
    logs = logs[logs["event"] == "task_response"]
    logs_by_user = logs.groupby("sid")
    sum_metric = 0
    for sid, group in logs_by_user:
        sum_metric += word_recognize_metric_for_word(group)
    return sum_metric / len(logs_by_user) 
    
    
def word_recognize_metric_for_word(session: pd.DataFrame) -> pd.Series:
    good_count = 0
    logs_by_word = session.groupby("word")

    for word_id, group in logs_by_word:
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
    return good_count / len(logs_by_word)