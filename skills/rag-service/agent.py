import argparse
import psycopg2
import requests
import os
import shutil
import uuid
import json
from html.parser import HTMLParser
from pdfminer.high_level import extract_text
import mimetypes

HAYSTACK_URL = "http://127.0.0.1:8000"
RAG_ROOT = "/mnt/data_disk/data/rag-docs"

def get_db_conn():
    return psycopg2.connect(dbname="vectordb", user="andrei", password="PostgressGreenCat1!", host="localhost", port="5432")

def create_tables():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
CREATE TABLE IF NOT EXISTS rag_groups (
  id      SERIAL PRIMARY KEY,
  name    TEXT UNIQUE NOT NULL,
  created TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rag_projects (
  id       SERIAL PRIMARY KEY,
  name     TEXT NOT NULL,
  group_id INT REFERENCES rag_groups(id) ON DELETE CASCADE,
  created  TIMESTAMPTZ DEFAULT now(),
  UNIQUE(name, group_id)
);

CREATE TABLE IF NOT EXISTS rag_documents (
  doc_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  filename    TEXT NOT NULL,
  mime_type   TEXT,
  stored_path TEXT NOT NULL,
  project_id  INT REFERENCES rag_projects(id) ON DELETE SET NULL,
  indexed_at  TIMESTAMPTZ DEFAULT now(),
  chunk_count INT DEFAULT 0
);
    """)
    conn.commit()
    cur.close()
    conn.close()

def create_dirs():
    os.makedirs(f"{RAG_ROOT}/originals", exist_ok=True)
    os.makedirs(f"{RAG_ROOT}/meta", exist_ok=True)

def chunk_text(text, chunk_size=375, overlap=37):
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = ' '.join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
    def handle_data(self, data):
        self.text.append(data.strip())

def extract_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.txt', '.md']:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    elif ext == '.pdf':
        return extract_text(file_path)
    elif ext == '.html':
        parser = TextExtractor()
        with open(file_path, 'r', encoding='utf-8') as f:
            parser.feed(f.read())
        return ' '.join(parser.text)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

def get_project_id(conn, group, project):
    cur = conn.cursor()
    cur.execute("SELECT p.id FROM rag_projects p JOIN rag_groups g ON p.group_id = g.id WHERE g.name=%s AND p.name=%s", (group, project))
    row = cur.fetchone()
    cur.close()
    if not row:
        raise ValueError(f"Project {project} not found in group {group}")
    return row[0]

def index_file(group, project, file_path):
    text = extract_text(file_path)
    chunks = chunk_text(text)
    doc_id = str(uuid.uuid4())
    filename = os.path.basename(file_path)
    mime_type = mimetypes.guess_type(file_path)[0]
    originals_path = f"{RAG_ROOT}/originals/{doc_id}{os.path.splitext(filename)[1]}"
    shutil.copy(file_path, originals_path)
    meta_path = f"{RAG_ROOT}/meta/{doc_id}.json"
    meta = {
        "doc_id": doc_id,
        "filename": filename,
        "mime_type": mime_type,
        "stored_path": originals_path,
        "group": group,
        "project": project,
        "chunk_count": len(chunks)
    }
    with open(meta_path, 'w') as f:
        json.dump(meta, f)
    conn = get_db_conn()
    project_id = get_project_id(conn, group, project)
    cur = conn.cursor()
    cur.execute("INSERT INTO rag_documents (doc_id, filename, mime_type, stored_path, project_id, chunk_count) VALUES (%s, %s, %s, %s, %s, %s)", (doc_id, filename, mime_type, originals_path, project_id, len(chunks)))
    conn.commit()
    docs = []
    for i, chunk in enumerate(chunks):
        docs.append({
            "content": chunk,
            "meta": {
                "doc_id": doc_id,
                "group": group,
                "project": project,
                "filename": filename,
                "chunk_index": i
            }
        })
    resp = requests.post(f"{HAYSTACK_URL}/documents/index", json={"documents": docs})
    resp.raise_for_status()
    cur.execute("UPDATE rag_documents SET indexed_at=now() WHERE doc_id=%s", (doc_id,))
    conn.commit()
    cur.close()
    conn.close()

def index_text(group, project, text, name):
    chunks = chunk_text(text)
    doc_id = str(uuid.uuid4())
    filename = name
    mime_type = "text/plain"
    originals_path = ""
    meta_path = f"{RAG_ROOT}/meta/{doc_id}.json"
    meta = {
        "doc_id": doc_id,
        "filename": filename,
        "mime_type": mime_type,
        "stored_path": originals_path,
        "group": group,
        "project": project,
        "chunk_count": len(chunks)
    }
    with open(meta_path, 'w') as f:
        json.dump(meta, f)
    conn = get_db_conn()
    project_id = get_project_id(conn, group, project)
    cur = conn.cursor()
    cur.execute("INSERT INTO rag_documents (doc_id, filename, mime_type, stored_path, project_id, chunk_count) VALUES (%s, %s, %s, %s, %s, %s)", (doc_id, filename, mime_type, originals_path, project_id, len(chunks)))
    conn.commit()
    docs = []
    for i, chunk in enumerate(chunks):
        docs.append({
            "content": chunk,
            "meta": {
                "doc_id": doc_id,
                "group": group,
                "project": project,
                "filename": filename,
                "chunk_index": i
            }
        })
    resp = requests.post(f"{HAYSTACK_URL}/documents/index", json={"documents": docs})
    resp.raise_for_status()
    cur.execute("UPDATE rag_documents SET indexed_at=now() WHERE doc_id=%s", (doc_id,))
    conn.commit()
    cur.close()
    conn.close()

def search_chunks(group, project=None, query="", top_k=5):
    conn = get_db_conn()
    cur = conn.cursor()
    if project:
        cur.execute("SELECT d.doc_id FROM rag_documents d JOIN rag_projects p ON d.project_id = p.id JOIN rag_groups g ON p.group_id = g.id WHERE g.name=%s AND p.name=%s", (group, project))
    else:
        cur.execute("SELECT d.doc_id FROM rag_documents d JOIN rag_projects p ON d.project_id = p.id JOIN rag_groups g ON p.group_id = g.id WHERE g.name=%s", (group,))
    doc_ids = set(row[0] for row in cur.fetchall())
    cur.close()
    conn.close()
    if not doc_ids:
        return []
    resp = requests.post(f"{HAYSTACK_URL}/documents/search", json={"query": query, "top_k": 100})
    resp.raise_for_status()
    results = resp.json()['results']
    filtered = [r for r in results if r['meta']['doc_id'] in doc_ids]
    return filtered[:top_k]

def list_docs(group, project=None):
    conn = get_db_conn()
    cur = conn.cursor()
    if project:
        cur.execute("SELECT d.doc_id, d.filename, d.mime_type, d.indexed_at, d.chunk_count FROM rag_documents d JOIN rag_projects p ON d.project_id = p.id JOIN rag_groups g ON p.group_id = g.id WHERE g.name=%s AND p.name=%s", (group, project))
    else:
        cur.execute("SELECT d.doc_id, d.filename, d.mime_type, d.indexed_at, d.chunk_count FROM rag_documents d JOIN rag_projects p ON d.project_id = p.id JOIN rag_groups g ON p.group_id = g.id WHERE g.name=%s", (group,))
    docs = cur.fetchall()
    cur.close()
    conn.close()
    return docs

def delete_doc(doc_id):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM rag_documents WHERE doc_id=%s", (doc_id,))
    conn.commit()
    cur.close()
    conn.close()
    meta_path = f"{RAG_ROOT}/meta/{doc_id}.json"
    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        stored_path = meta.get('stored_path')
        if stored_path and os.path.exists(stored_path):
            os.remove(stored_path)
        os.remove(meta_path)

def move_doc(doc_id, to_group, to_project):
    conn = get_db_conn()
    project_id = get_project_id(conn, to_group, to_project)
    cur = conn.cursor()
    cur.execute("UPDATE rag_documents SET project_id=%s WHERE doc_id=%s", (project_id, doc_id))
    conn.commit()
    cur.close()
    conn.close()
    meta_path = f"{RAG_ROOT}/meta/{doc_id}.json"
    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        meta['group'] = to_group
        meta['project'] = to_project
        with open(meta_path, 'w') as f:
            json.dump(meta, f)

def groups_list():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT name, created FROM rag_groups ORDER BY created")
    groups = cur.fetchall()
    cur.close()
    conn.close()
    return groups

def groups_create(name):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO rag_groups (name) VALUES (%s)", (name,))
    conn.commit()
    cur.close()
    conn.close()

def projects_list(group):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT p.name, p.created FROM rag_projects p JOIN rag_groups g ON p.group_id = g.id WHERE g.name=%s ORDER BY p.created", (group,))
    projects = cur.fetchall()
    cur.close()
    conn.close()
    return projects

def projects_create(name, group):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO rag_projects (name, group_id) VALUES (%s, (SELECT id FROM rag_groups WHERE name=%s))", (name, group))
    conn.commit()
    cur.close()
    conn.close()

def projects_move(name, from_group, to_group):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("UPDATE rag_projects SET group_id = (SELECT id FROM rag_groups WHERE name=%s) WHERE name=%s AND group_id = (SELECT id FROM rag_groups WHERE name=%s)", (to_group, name, from_group))
    conn.commit()
    cur.close()
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="RAG Service CLI")
    subparsers = parser.add_subparsers(dest='command')
    # init
    subparsers.add_parser('init')
    # groups
    groups_parser = subparsers.add_parser('groups')
    groups_sub = groups_parser.add_subparsers(dest='subcommand')
    groups_sub.add_parser('list')
    create_group = groups_sub.add_parser('create')
    create_group.add_argument('name')
    # projects
    projects_parser = subparsers.add_parser('projects')
    projects_sub = projects_parser.add_subparsers(dest='subcommand')
    list_proj = projects_sub.add_parser('list')
    list_proj.add_argument('--group', required=True)
    create_proj = projects_sub.add_parser('create')
    create_proj.add_argument('name')
    create_proj.add_argument('--group', required=True)
    move_proj = projects_sub.add_parser('move')
    move_proj.add_argument('name')
    move_proj.add_argument('--from-group', required=True)
    move_proj.add_argument('--to-group', required=True)
    # index
    index_parser = subparsers.add_parser('index')
    index_parser.add_argument('--group', required=True)
    index_parser.add_argument('--project', required=True)
    index_parser.add_argument('--file')
    index_parser.add_argument('--text')
    index_parser.add_argument('--name')
    # search
    search_parser = subparsers.add_parser('search')
    search_parser.add_argument('--group', required=True)
    search_parser.add_argument('--project')
    search_parser.add_argument('--query', required=True)
    search_parser.add_argument('--top-k', type=int, default=5)
    # chat
    chat_parser = subparsers.add_parser('chat')
    chat_parser.add_argument('--group', required=True)
    chat_parser.add_argument('--project')
    chat_parser.add_argument('--question', required=True)
    # list
    list_parser = subparsers.add_parser('list')
    list_parser.add_argument('--group', required=True)
    list_parser.add_argument('--project')
    # delete
    delete_parser = subparsers.add_parser('delete')
    delete_parser.add_argument('--doc-id', required=True)
    # move
    move_parser = subparsers.add_parser('move')
    move_parser.add_argument('--doc-id', required=True)
    move_parser.add_argument('--to-project', required=True)
    move_parser.add_argument('--to-group', required=True)
    args = parser.parse_args()
    if args.command == 'init':
        create_tables()
        create_dirs()
        print("Initialized")
    elif args.command == 'groups':
        if args.subcommand == 'list':
            groups = groups_list()
            for name, created in groups:
                print(f"{name} - {created}")
        elif args.subcommand == 'create':
            groups_create(args.name)
            print(f"Created group {args.name}")
    elif args.command == 'projects':
        if args.subcommand == 'list':
            projects = projects_list(args.group)
            for name, created in projects:
                print(f"{name} - {created}")
        elif args.subcommand == 'create':
            projects_create(args.name, args.group)
            print(f"Created project {args.name} in {args.group}")
        elif args.subcommand == 'move':
            projects_move(args.name, args.from_group, args.to_group)
            print(f"Moved project {args.name} from {args.from_group} to {args.to_group}")
    elif args.command == 'index':
        if args.file:
            index_file(args.group, args.project, args.file)
            print("Indexed file")
        elif args.text and args.name:
            index_text(args.group, args.project, args.text, args.name)
            print("Indexed text")
        else:
            print("Specify --file or --text with --name")
    elif args.command == 'search':
        results = search_chunks(args.group, args.project, args.query, args.top_k)
        for r in results:
            print(f"Score: {r['score']}\nContent: {r['content']}\nMeta: {r['meta']}\n---")
    elif args.command == 'chat':
        results = search_chunks(args.group, args.project, args.question, 5)
        print(f"Top chunks for question: {args.question}\n")
        for r in results:
            print(f"From {r['meta']['filename']} (chunk {r['meta']['chunk_index']}):\n{r['content']}\n")
    elif args.command == 'list':
        docs = list_docs(args.group, args.project)
        for doc_id, filename, mime, indexed, chunks in docs:
            print(f"{doc_id} - {filename} - {mime} - {indexed} - {chunks} chunks")
    elif args.command == 'delete':
        delete_doc(args.doc_id)
        print(f"Deleted {args.doc_id}")
    elif args.command == 'move':
        move_doc(args.doc_id, args.to_group, args.to_project)
        print(f"Moved {args.doc_id} to {args.to_group}/{args.to_project}")
    else:
        parser.print_help()

if __name__ == '__main__':
    main()