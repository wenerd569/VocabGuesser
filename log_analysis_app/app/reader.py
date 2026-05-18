from pathlib import Path
import pandas as pd

LOG_PATH = "/home/wenerd/Documents/VocabGuesser/logs/logs.jsonl"

def get_logs():
    return pd.read_json(LOG_PATH, lines=True)