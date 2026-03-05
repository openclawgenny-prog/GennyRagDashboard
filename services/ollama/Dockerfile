FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV MODEL_NAME=all-minilm:latest
ENV OLLAMA_HOST=0.0.0.0:11434

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

RUN mkdir -p /var/lib/ollama

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 11434

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
