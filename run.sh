#!/usr/bin/env bash
set -euo pipefail

IMAGE=quizlet-v0

cd "$(dirname "$0")"

mkdir -p logs

# Check if Podman is available, otherwise use Docker
if command -v podman &> /dev/null; then
    echo "Using Podman..."
    podman build -t "$IMAGE" .
    podman run --rm -it \
      -p 8000:8000 \
      -v "$(pwd)/data:/app/data" \
      -v "$(pwd)/presets:/app/presets:ro" \
      -v "$(pwd)/logs:/app/logs" \
      --env-file .env \
      "$IMAGE"
elif command -v docker &> /dev/null; then
    echo "Using Docker..."
    docker build -t "$IMAGE" .
    docker run --rm -it \
      --network=host \
      -v "$(pwd)/data:/app/data" \
      -v "$(pwd)/presets:/app/presets:ro" \
      -v "$(pwd)/logs:/app/logs" \
      -e http_proxy=http://127.0.0.1:1080 \
      -e https_proxy=http://127.0.0.1:1080 \
      -e all_proxy=http://127.0.0.1:1080 \
      -e no_proxy=localhost,127.0.0.1 \
      --env-file .env \
      "$IMAGE"
else
    echo "Error: Neither Podman nor Docker is installed"
    exit 1
fi
