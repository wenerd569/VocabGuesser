import pandas as pd

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent.parent))

    from app.reader import get_logs
    from app.metrics import word_memorize_metric, like_metric
    from app.metrics_runner import run_metrics_by_session
else:
    from .reader import get_logs
    from .metrics import word_memorize_metric, like_metric
    from .metrics_runner import run_metrics_by_session



def show_metrics_pandas(results_df: pd.DataFrame) -> pd.DataFrame:
    """Показывает `results_df` средствами pandas/IPython и возвращает его.

    В среде Jupyter будет использован `IPython.display.display` для красивого отображения.
    В консоли просто возвращаем DataFrame (и в крайнем случае выводим to_string).
    """
    if results_df.empty:
        return results_df

    try:
        from IPython.display import display
        display(results_df)
    except Exception:
        try:
            print(results_df.to_string(index=False))
        except Exception:
            pass

    return results_df


if __name__ == '__main__':
    path = ""
    
    df = get_logs()

    metrics = {
        'word_memorize': word_memorize_metric,
        'user_like': like_metric,
    }

    results = run_metrics_by_session(df, metrics)
    show_metrics_pandas(results)
