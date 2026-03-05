# RAG Service Skill

This skill provides a command-line interface for managing a RAG (Retrieval-Augmented Generation) document service using OpenClaw. It allows organizing documents into groups and projects, indexing them into a vector database via Haystack, and performing semantic search and chat.

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Initialize the service:**
   ```bash
   python3 agent.py init
   ```
   This creates the necessary database tables and directories.

3. **Create a group and project:**
   ```bash
   python3 agent.py groups create mygroup
   python3 agent.py projects create myproject --group mygroup
   ```

4. **Index a document:**
   ```bash
   python3 agent.py index --group mygroup --project myproject --file /path/to/document.pdf
   ```

5. **Search or chat:**
   ```bash
   python3 agent.py search --group mygroup --query "What is machine learning?"
   python3 agent.py chat --group mygroup --question "Explain AI concepts"
   ```

## Architecture

- **Storage:** Documents are stored in `/mnt/data_disk/data/rag-docs/`, with originals in `originals/` and metadata in `meta/`.
- **Database:** Uses PostgreSQL for organizing groups, projects, and documents.
- **Indexing:** Documents are chunked and indexed into Haystack for semantic search.
- **API:** Interacts with Haystack API at `http://127.0.0.1:8000`.

For full command details, see `SKILL.md`.