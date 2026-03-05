#!/usr/bin/env bash
set -euo pipefail

MODEL_NAME="${MODEL_NAME:-all-minilm:latest}"
OLLAMA_HOST="${OLLAMA_HOST:-0.0.0.0:11434}"

log() { printf "%s %s\n" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$*"; }

log "Starting Ollama server on $OLLAMA_HOST"
export OLLAMA_HOST="$OLLAMA_HOST"

# Start ollama serve in background
ollama serve &
SERVE_PID=$!

# Wait for server to be ready
log "Waiting for Ollama to become ready..."
for i in $(seq 1 30); do
  if curl -sf "http://localhost:11434/" >/dev/null 2>&1; then
    log "Ollama is ready"
    break
  fi
  sleep 1
done

# Pull the model
log "Pulling model: $MODEL_NAME"
attempt=0
max_attempts=5
while [ $attempt -lt $max_attempts ]; do
  attempt=$((attempt+1))
  if ollama pull "$MODEL_NAME"; then
    log "Model $MODEL_NAME pulled successfully"
    break
  fi
  log "Pull attempt $attempt failed, retrying..."
  sleep $((2**attempt))
done

# Keep foreground process alive
wait $SERVE_PID
