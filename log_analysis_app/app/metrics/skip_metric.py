import pandas as pd


def skip_metric(logs: pd.DataFrame) -> float:
    skip_events = logs[logs["event"] == "task_skip"]
    return len(skip_events) / len(logs)