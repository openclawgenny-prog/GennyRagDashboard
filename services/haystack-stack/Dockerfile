FROM deepset/haystack:base-v2.12.1

# Install pgvector integration + SentenceTransformers + uvicorn/fastapi
RUN pip install --no-cache-dir \
    haystack-ai \
    pgvector-haystack \
    sentence-transformers \
    fastapi \
    uvicorn[standard] \
    psycopg2-binary

# Copy pipeline server
COPY pipeline.py /app/pipeline.py

WORKDIR /app

CMD ["python3", "/app/pipeline.py"]
