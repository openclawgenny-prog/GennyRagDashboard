#!/usr/bin/env python3
"""
Haystack v2 pipeline server
  - PgvectorDocumentStore  (postgres-pgvector)
  - Embeddings via Ollama  (all-minilm:latest — already running in ollama container)
  - FastAPI REST API
  - NO torch / NO sentence-transformers / NO CUDA
"""

import os, time, logging, socket, json
from typing import List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from haystack import Document
from haystack_integrations.document_stores.pgvector import PgvectorDocumentStore
from haystack_integrations.components.retrievers.pgvector import PgvectorEmbeddingRetriever

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("haystack-server")

# ── Config ───────────────────────────────────────────────────────────────────
PG_HOST     = os.environ.get("POSTGRES_HOST",     "postgres-pgvector-db-1")
PG_PORT     = os.environ.get("POSTGRES_PORT",     "5432")
PG_DB       = os.environ.get("POSTGRES_DB",       "vectordb")
PG_USER     = os.environ.get("POSTGRES_USER",     "andrei")
PG_PASS     = os.environ.get("POSTGRES_PASSWORD", "PostgressGreenCat1!")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST",       "ollama")
OLLAMA_PORT = os.environ.get("OLLAMA_PORT",       "11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL",       "all-minilm:latest")
API_HOST    = os.environ.get("HAYSTACK_API_HOST", "0.0.0.0")
API_PORT    = int(os.environ.get("HAYSTACK_API_PORT", "8000"))

OLLAMA_URL  = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
PG_DSN      = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"

# ── Helpers ──────────────────────────────────────────────────────────────────
def wait_for(host, port, label, retries=30, delay=3.0):
    log.info(f"Waiting for {label} at {host}:{port} ...")
    for i in range(retries):
        try:
            with socket.create_connection((host, int(port)), timeout=3):
                log.info(f"  {label} ready ✅")
                return
        except OSError:
            log.info(f"  {label} not ready ({i+1}/{retries}), retrying...")
            time.sleep(delay)
    raise RuntimeError(f"{label} at {host}:{port} unreachable after {retries} retries")

def embed(texts: list[str]) -> list[list[float]]:
    """Call Ollama /api/embed to get embeddings for a list of texts."""
    r = httpx.post(
        f"{OLLAMA_URL}/api/embed",
        json={"model": EMBED_MODEL, "input": texts},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["embeddings"]

# ── Startup ──────────────────────────────────────────────────────────────────
wait_for(PG_HOST,     PG_PORT,     "Postgres")
wait_for(OLLAMA_HOST, OLLAMA_PORT, "Ollama")

# Verify embed model responds
log.info(f"Testing embed model {EMBED_MODEL} via Ollama ...")
test_vec = embed(["hello world"])
EMBED_DIM = len(test_vec[0])
log.info(f"  embed dim={EMBED_DIM} ✅")

# Wrap DSN in Secret for haystack-integrations compatibility
try:
    from haystack.utils import Secret
    _conn_str = Secret.from_token(PG_DSN)
except (ImportError, AttributeError):
    try:
        from haystack import Secret
        _conn_str = Secret.from_token(PG_DSN)
    except (ImportError, AttributeError):
        _conn_str = PG_DSN  # fallback for older versions

log.info("Initialising PgvectorDocumentStore ...")
document_store = PgvectorDocumentStore(
    connection_string=_conn_str,
    table_name="haystack_docs",
    embedding_dimension=EMBED_DIM,
    vector_function="cosine_similarity",
    recreate_table=False,
    search_strategy="hnsw",
)
log.info("DocumentStore ready ✅")

retriever = PgvectorEmbeddingRetriever(document_store=document_store, top_k=5)

# ── FastAPI ───────────────────────────────────────────────────────────────────
app = FastAPI(title="Haystack API", version="2.0")

class IndexRequest(BaseModel):
    documents: List[dict]   # [{"content": "...", "meta": {...}}]

class SearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5


@app.get("/health")
def health():
    return {
        "status": "ok",
        "store": "pgvector",
        "embed_model": EMBED_MODEL,
        "ollama": OLLAMA_URL,
        "doc_count": document_store.count_documents(),
    }

@app.get("/documents/count")
def count():
    return {"count": document_store.count_documents()}

@app.post("/documents/index")
def index_documents(req: IndexRequest):
    texts = [d.get("content", "") for d in req.documents]
    embeddings = embed(texts)
    docs = [
        Document(content=d.get("content", ""), embedding=emb, meta=d.get("meta", {}))
        for d, emb in zip(req.documents, embeddings)
    ]
    document_store.write_documents(docs)
    return {"indexed": len(docs)}

@app.post("/documents/search")
def search(req: SearchRequest):
    retriever.top_k = req.top_k or 5
    query_emb = embed([req.query])[0]
    results = retriever.run(query_embedding=query_emb)
    return {
        "query": req.query,
        "results": [
            {"content": d.content, "score": d.score, "meta": d.meta}
            for d in results["documents"]
        ],
    }

@app.delete("/documents")
def delete_all():
    all_docs = document_store.filter_documents()
    document_store.delete_documents(all_docs)
    return {"deleted": len(all_docs)}


if __name__ == "__main__":
    log.info(f"Starting Haystack REST API on {API_HOST}:{API_PORT}")
    uvicorn.run(app, host=API_HOST, port=API_PORT)
