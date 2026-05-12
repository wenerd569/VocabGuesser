#!/usr/bin/env bash
set -euo pipefail

IMAGE=quizlet-v0

cd "$(dirname "$0")"

mkdir -p logs

docker build -t "$IMAGE" .
docker run --rm -it \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/presets:/app/presets:ro" \
  -v "$(pwd)/logs:/app/logs" \
  "$IMAGE"
