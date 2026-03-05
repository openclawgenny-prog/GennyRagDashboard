Ollama single-container runner

This folder contains a minimal Docker project to run Ollama and load the all-minilm:latest model at container start (the model is downloaded into a cache directory at runtime).

Files:
- Dockerfile — builds a small image (python:3.11-slim base) and optionally downloads an Ollama binary at build time via the OLLAMA_URL build-arg.
- entrypoint.sh — downloads/pulls the model (uses "ollama pull") with retry/backoff, then starts the Ollama server.
- .dockerignore — standard ignores.
- portainer_container_spec.json — Portainer container spec template.

Build locally:
  docker build -t ghcr.io/<owner>/ollama-all-minilm:latest .

Run locally (example):
  docker run -it --rm \
    -v /mnt/data_disk/models:/var/lib/ollama \
    -p 11434:11434 \
    ghcr.io/<owner>/ollama-all-minilm:latest

Notes:
- The Dockerfile expects an Ollama binary if you provide OLLAMA_URL as a build-arg. If you don't have a binary, modify the Dockerfile to install the proper runtime or add instructions to the README.
- Persistent model cache: mount /mnt/data_disk/models on the host to /var/lib/ollama in the container to avoid re-downloading the model on restart.
- Healthcheck: Ollama typically exposes a health endpoint; adjust the healthcheck to match the actual server endpoints.
