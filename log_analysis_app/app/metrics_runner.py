import pandas as pd
from typing import Callable, Dict, Any
import os


def run_metrics_by_session(logs: pd.DataFrame, metrics: Dict[str, Callable[[pd.DataFrame], Any]]) -> pd.DataFrame:
    """Разбивает логи по сессиям (колонка 'sid') и запускает переданные метрики.

    Возвращает DataFrame с колонкой 'sid' и результатами каждой метрики.
    """
    if 'sid' not in logs.columns:
        raise ValueError("Logs must contain 'sid' column to split by sessions")

    results = []
    sessions = logs.groupby('sid')
    for sid, session_df in sessions:
        row = {'sid': sid}
        for name, fn in metrics.items():
            try:
                row[name] = fn(session_df)
            except Exception:
                row[name] = None
        results.append(row)

    return pd.DataFrame(results)

