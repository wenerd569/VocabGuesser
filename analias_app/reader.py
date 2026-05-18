from pathlib import Path
import pandas as pd

LOG_PATH = Path(__file__).parent / "logs" / "logs.jsonl"

def get_logs():
    return pd.read_json(LOG_PATH, lines=True)