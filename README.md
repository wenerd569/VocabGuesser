# VocabGuesser

VocabGuesser is a FastAPI app for vocabulary cards and grammar practice.

## Synthetic cards dataset runner

`app/synthetic_cards_runner.py` simulates a B2 learner on the **cards flow** and writes a JSONL dataset.
It uses an OpenAI-compatible chat API (Groq OpenAI endpoint supported).

### 1. Start the app

```bash
DATA_DIR="$(pwd)/data" \
PRESETS_DIR="$(pwd)/presets" \
LOGS_DIR="$(pwd)/logs" \
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2. Configure API access

Set either `OPENAI_API_KEY` or `GROQ_API_KEY`. Optional overrides:

- `OPENAI_BASE_URL` (default: `https://api.groq.com/openai/v1`)
- `OPENAI_MODEL` (default: `openai/gpt-oss-20b`)

### 3. Generate dataset

```bash
uv run python -m app.synthetic_cards_runner \
  --app-url http://127.0.0.1:8000 \
  --sessions 2 \
  --turns 30 \
  --output data/synthetic_cards_dataset.jsonl \
  --logs-path logs/logs.jsonl \
  --model openai/gpt-oss-20b
```

The output JSONL contains interaction rows and per-session summary rows with `sid`-linked log event counts.
