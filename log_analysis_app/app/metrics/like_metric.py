import pandas as pd


def like_metric(logs: pd.DataFrame) -> float:
    marks = logs[logs["event"] == "pack_marked"]["mark"].tolist()
    if not marks:
        return 0.0

    res = 0
    for mark in marks:
        if mark == "like":
            res += 1
        if mark == "dislike":
            res -= 1

    return res / len(marks)
