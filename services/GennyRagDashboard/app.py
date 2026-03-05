import os
import json
import bcrypt
import subprocess
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Request, Response, HTTPException, UploadFile, File, Form, Query
from starlette.responses import HTMLResponse, RedirectResponse
from itsdangerous import URLSafeTimedSerializer

CONFIG_FILE = 'config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {"username": "admin", "password_hash": "$2b$12$nW60m18sg845j0nccRS6AerpyoC7g1oehlK3574kioSHzqFOQnf2u", "first_login": True}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

config = load_config()

app = FastAPI()

secret_key = "my_secret_key_12345"
serializer = URLSafeTimedSerializer(secret_key)

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="vectordb",
        user="andrei",
        password="PostgressGreenCat1!"
    )

def get_groups():
    conn = get_db_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT DISTINCT group_name FROM documents ORDER BY group_name")
        groups = cur.fetchall()
        for g in groups:
            cur.execute("SELECT DISTINCT project_name FROM documents WHERE group_name = %s ORDER BY project_name", (g['group_name'],))
            g['projects'] = [p['project_name'] for p in cur.fetchall()]
    conn.close()
    return groups

def get_documents(group=None, project=None):
    conn = get_db_connection()
    query = "SELECT id, filename, group_name, project_name, chunks, created_at FROM documents"
    params = []
    where_clauses = []
    if group:
        where_clauses.append("group_name = %s")
        params.append(group)
    if project:
        where_clauses.append("project_name = %s")
        params.append(project)
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY created_at DESC"
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        docs = cur.fetchall()
    conn.close()
    return docs

def get_stats():
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM documents")
        doc_count = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(SUM(chunks), 0) FROM documents")
        chunk_count = cur.fetchone()[0]
    conn.close()
    haystack_ok = False
    try:
        response = requests.get("http://127.0.0.1:8000/status", timeout=5)
        haystack_ok = response.status_code == 200
    except:
        pass
    return {"doc_count": doc_count, "chunk_count": chunk_count, "haystack_ok": haystack_ok}

@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    session = request.cookies.get('session')
    if session:
        try:
            username = serializer.loads(session, max_age=3600)
            if config.get('first_login', False):
                return RedirectResponse("/settings")
            return dashboard_html()
        except:
            pass
    return login_html()

def login_html():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Login</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>
tailwind.config = {
  darkMode: 'class',
}
</script>
</head>
<body class="bg-gray-900 text-white min-h-screen flex items-center justify-center">
<form method="post" action="/login" class="bg-gray-800 p-8 rounded-lg shadow-lg w-full max-w-sm">
<h2 class="text-2xl mb-4 text-center">Login</h2>
<div class="mb-4">
<label class="block text-sm font-medium mb-2">Username</label>
<input name="username" class="w-full p-2 bg-gray-700 rounded" required>
</div>
<div class="mb-4">
<label class="block text-sm font-medium mb-2">Password</label>
<input type="password" name="password" class="w-full p-2 bg-gray-700 rounded" required>
</div>
<button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 p-2 rounded">Login</button>
</form>
</body>
</html>
"""

def dashboard_html():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>RAG Dashboard</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>
tailwind.config = {
  darkMode: 'class',
}
</script>
<style>
body { font-family: 'Inter', sans-serif; }
</style>
</head>
<body class="bg-gray-900 text-white min-h-screen">
<div id="stats" class="p-4 bg-gray-800 text-center text-lg"></div>
<div class="flex">
<div id="sidebar" class="w-1/4 p-4 bg-gray-800 min-h-screen"></div>
<div class="w-3/4 p-4">
<div class="mb-4">
<input id="search-query" class="p-2 bg-gray-700 rounded w-3/4" placeholder="Search query">
<button onclick="search()" class="ml-2 p-2 bg-blue-600 hover:bg-blue-700 rounded">Search</button>
</div>
<div id="search-results" class="mb-4"></div>
<div id="upload" class="mb-4 p-4 bg-gray-800 rounded">
<h3 class="text-xl mb-2">Upload Document</h3>
<form enctype="multipart/form-data" method="post" action="/api/upload" onsubmit="return handleUpload(event)">
<input type="file" name="file" class="mb-2 p-2 bg-gray-700 rounded w-full" required>
<select name="group" onchange="loadProjects(this.value)" class="mb-2 p-2 bg-gray-700 rounded w-full" required>
<option value="">Select Group</option>
</select>
<select name="project" class="mb-2 p-2 bg-gray-700 rounded w-full" required>
<option value="">Select Project</option>
</select>
<button type="submit" class="p-2 bg-green-600 hover:bg-green-700 rounded">Upload</button>
</form>
</div>
<div id="documents"></div>
</div>
</div>
<script>
let currentGroup = '';
let currentProject = '';
async function loadStats() {
    const res = await fetch('/api/stats');
    const stats = await res.json();
    document.getElementById('stats').innerHTML = `Total Docs: ${stats.doc_count} | Total Chunks: ${stats.chunk_count} | Haystack: <span class="${stats.haystack_ok ? 'text-green-500' : 'text-red-500'}">${stats.haystack_ok ? 'OK' : 'ERROR'}</span>`;
}
async function loadGroups() {
    const res = await fetch('/api/groups');
    const groups = await res.json();
    let html = '<h3 class="text-xl mb-2">Groups/Projects</h3>';
    for (const g of groups) {
        html += `<div class="mb-2"><div class="font-bold cursor-pointer hover:text-blue-400" onclick="filterGroup('${g.group_name}')">${g.group_name}</div>`;
        for (const p of g.projects) {
            html += `<div class="ml-4 cursor-pointer hover:text-blue-400" onclick="filterProject('${g.group_name}', '${p}')">${p}</div>`;
        }
        html += '</div>';
    }
    document.getElementById('sidebar').innerHTML = html;
}
function filterGroup(g) {
    currentGroup = g;
    currentProject = '';
    loadDocuments();
}
function filterProject(g, p) {
    currentGroup = g;
    currentProject = p;
    loadDocuments();
}
async function loadDocuments() {
    const params = new URLSearchParams();
    if (currentGroup) params.append('group', currentGroup);
    if (currentProject) params.append('project', currentProject);
    const res = await fetch(`/api/documents?${params}`);
    const docs = await res.json();
    let html = '<h3 class="text-xl mb-2">Documents</h3><table class="w-full table-auto"><thead><tr class="bg-gray-800"><th class="p-2">Filename</th><th class="p-2">Group</th><th class="p-2">Project</th><th class="p-2">Chunks</th><th class="p-2">Date</th><th class="p-2">Actions</th></tr></thead><tbody>';
    for (const d of docs) {
        html += `<tr class="border-b border-gray-700"><td class="p-2">${d.filename}</td><td class="p-2">${d.group_name}</td><td class="p-2">${d.project_name}</td><td class="p-2">${d.chunks}</td><td class="p-2">${new Date(d.created_at).toLocaleDateString()}</td><td class="p-2"><button onclick="deleteDoc(${d.id})" class="mr-2 p-1 bg-red-600 hover:bg-red-700 rounded">Delete</button><button onclick="moveDoc(${d.id})" class="p-1 bg-yellow-600 hover:bg-yellow-700 rounded">Move</button></td></tr>`;
    }
    html += '</tbody></table>';
    document.getElementById('documents').innerHTML = html;
}
async function search() {
    const query = document.getElementById('search-query').value;
    if (!query) return;
    const res = await fetch('/api/search', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({query, group: currentGroup, project: currentProject, top_k: 10})
    });
    const results = await res.json();
    let html = '<h4 class="text-lg mb-2">Search Results</h4>';
    for (const r of results) {
        html += `<div class="mb-2 p-2 bg-gray-800 rounded"><strong>Score: ${r.score.toFixed(2)}</strong><br>${r.content}</div>`;
    }
    document.getElementById('search-results').innerHTML = html;
}
async function deleteDoc(id) {
    if (confirm('Are you sure you want to delete this document?')) {
        await fetch(`/api/documents/${id}`, {method: 'DELETE'});
        loadDocuments();
    }
}
async function moveDoc(id) {
    const toGroup = prompt('New Group:');
    const toProject = prompt('New Project:');
    if (toGroup && toProject) {
        await fetch(`/api/documents/${id}/move`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({to_group: toGroup, to_project: toProject})
        });
        loadDocuments();
    }
}
async function loadUploadOptions() {
    const res = await fetch('/api/groups');
    const groups = await res.json();
    let groupHtml = '<option value="">Select Group</option>';
    for (const g of groups) {
        groupHtml += `<option value="${g.group_name}">${g.group_name}</option>`;
    }
    document.querySelector('select[name="group"]').innerHTML = groupHtml;
}
function loadProjects(group) {
    if (!group) {
        document.querySelector('select[name="project"]').innerHTML = '<option value="">Select Project</option>';
        return;
    }
    fetch('/api/groups').then(res => res.json()).then(groups => {
        const g = groups.find(g => g.group_name === group);
        if (g) {
            let projectHtml = '<option value="">Select Project</option>';
            for (const p of g.projects) {
                projectHtml += `<option value="${p}">${p}</option>`;
            }
            document.querySelector('select[name="project"]').innerHTML = projectHtml;
        }
    });
}
async function handleUpload(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData
    });
    if (res.ok) {
        alert('Upload successful');
        loadDocuments();
    } else {
        alert('Upload failed');
    }
}
window.onload = () => {
    loadStats();
    loadGroups();
    loadUploadOptions();
    loadDocuments();
};
</script>
</body>
</html>
"""

@app.get("/settings", response_class=HTMLResponse)
def settings(request: Request):
    session = request.cookies.get('session')
    if not session:
        return RedirectResponse("/")
    try:
        serializer.loads(session, max_age=3600)
    except:
        return RedirectResponse("/")
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Settings</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>
tailwind.config = {{
  darkMode: 'class',
}}
</script>
</head>
<body class="bg-gray-900 text-white min-h-screen flex items-center justify-center">
<form method="post" action="/settings" class="bg-gray-800 p-8 rounded-lg shadow-lg w-full max-w-sm">
<h2 class="text-2xl mb-4 text-center">Settings</h2>
<div class="mb-4">
<label class="block text-sm font-medium mb-2">Username</label>
<input name="username" value="{config['username']}" class="w-full p-2 bg-gray-700 rounded" required>
</div>
<div class="mb-4">
<label class="block text-sm font-medium mb-2">New Password</label>
<input type="password" name="password" class="w-full p-2 bg-gray-700 rounded">
</div>
<button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 p-2 rounded">Update</button>
</form>
</body>
</html>
"""

@app.post("/login")
def login(response: Response, username: str = Form(...), password: str = Form(...)):
    if username == config['username'] and bcrypt.checkpw(password.encode(), config['password_hash'].encode()):
        token = serializer.dumps(username)
        response.set_cookie('session', token, httponly=True)
        if config.get('first_login', False):
            return RedirectResponse("/settings", status_code=303)
        return RedirectResponse("/", status_code=303)
    raise HTTPException(401, "Invalid credentials")

@app.get("/logout")
def logout(response: Response):
    response.delete_cookie('session')
    return RedirectResponse("/")

@app.get("/api/stats")
def api_stats():
    return get_stats()

@app.get("/api/groups")
def api_groups():
    return get_groups()

@app.get("/api/documents")
def api_documents(group: str = Query(None), project: str = Query(None)):
    return get_documents(group, project)

@app.post("/api/upload")
def api_upload(file: UploadFile = File(...), group: str = Form(...), project: str = Form(...)):
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(file.file.read())
    result = subprocess.run(["python3", "/home/andrei/.openclaw/workspace/skills/rag-service/agent.py", "index", temp_path, group, project], capture_output=True, text=True)
    os.remove(temp_path)
    if result.returncode == 0:
        return {"status": "ok"}
    raise HTTPException(500, f"Upload failed: {result.stderr}")

@app.delete("/api/documents/{doc_id}")
def api_delete(doc_id: int):
    result = subprocess.run(["python3", "/home/andrei/.openclaw/workspace/skills/rag-service/agent.py", "delete", str(doc_id)], capture_output=True, text=True)
    if result.returncode == 0:
        return {"status": "ok"}
    raise HTTPException(500, f"Delete failed: {result.stderr}")

@app.post("/api/documents/{doc_id}/move")
def api_move(doc_id: int, body: dict):
    to_group = body['to_group']
    to_project = body['to_project']
    result = subprocess.run(["python3", "/home/andrei/.openclaw/workspace/skills/rag-service/agent.py", "move", str(doc_id), to_group, to_project], capture_output=True, text=True)
    if result.returncode == 0:
        return {"status": "ok"}
    raise HTTPException(500, f"Move failed: {result.stderr}")

@app.post("/api/search")
def api_search(body: dict):
    query = body['query']
    group = body.get('group', '')
    project = body.get('project', '')
    top_k = body.get('top_k', 10)
    payload = {"query": query, "filters": {}, "top_k": top_k}
    if group:
        payload["filters"]["group"] = group
    if project:
        payload["filters"]["project"] = project
    try:
        response = requests.post("http://127.0.0.1:8000/query", json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("documents", [])
        else:
            raise HTTPException(500, f"Haystack error: {response.status_code}")
    except requests.RequestException as e:
        raise HTTPException(500, f"Haystack request failed: {str(e)}")

@app.post("/settings")
def update_settings(response: Response, username: str = Form(...), password: str = Form(...)):
    config['username'] = username
    if password:
        config['password_hash'] = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    config['first_login'] = False
    save_config(config)
    return RedirectResponse("/", status_code=303)