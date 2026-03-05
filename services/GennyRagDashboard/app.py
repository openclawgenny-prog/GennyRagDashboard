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
<title>Genny RAG Dashboard</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
body { font-family: 'Inter', sans-serif; background: #0f172a; color: #e2e8f0; }
.sidebar-group { border-left: 3px solid #334155; }
.sidebar-group.active { border-left-color: #6366f1; }
.sidebar-project.active { color: #818cf8; font-weight: 600; }
.modal { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.7); z-index:50; align-items:center; justify-content:center; }
.modal.open { display:flex; }
</style>
</head>
<body class="min-h-screen">

<!-- Top bar -->
<div class="flex items-center justify-between px-6 py-3 bg-slate-800 border-b border-slate-700">
  <div class="flex items-center gap-2">
    <span class="text-xl">🗄️</span>
    <span class="font-bold text-indigo-400 text-lg">Genny RAG Dashboard</span>
  </div>
  <div id="stats" class="flex gap-6 text-sm text-slate-400"></div>
  <a href="/logout" class="text-xs text-slate-500 hover:text-white">Logout</a>
</div>

<div class="flex h-[calc(100vh-52px)]">

  <!-- Sidebar -->
  <div class="w-64 bg-slate-800 border-r border-slate-700 flex flex-col overflow-hidden">
    <div class="flex items-center justify-between px-4 py-3 border-b border-slate-700">
      <span class="text-xs uppercase tracking-wider text-slate-400">Groups</span>
      <button onclick="openModal('group-modal')" class="text-indigo-400 hover:text-indigo-300 text-lg font-bold" title="Add Group">＋</button>
    </div>
    <div id="sidebar-tree" class="flex-1 overflow-y-auto py-2"></div>

    <!-- Add Project button (visible when group selected) -->
    <div id="add-project-bar" class="hidden px-4 py-3 border-t border-slate-700">
      <button onclick="openModal('project-modal')" class="w-full text-sm bg-indigo-700 hover:bg-indigo-600 rounded px-3 py-1">
        + Add Project to <span id="add-project-label" class="font-bold"></span>
      </button>
    </div>
  </div>

  <!-- Main content -->
  <div class="flex-1 flex flex-col overflow-hidden">

    <!-- Search bar -->
    <div class="px-6 py-3 bg-slate-900 border-b border-slate-700 flex gap-2">
      <input id="search-query" class="flex-1 p-2 bg-slate-700 rounded text-sm" placeholder="Semantic search…">
      <button onclick="doSearch()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded text-sm">Search</button>
      <button onclick="clearSearch()" class="px-3 py-2 bg-slate-600 hover:bg-slate-500 rounded text-sm">Clear</button>
    </div>

    <div class="flex-1 overflow-y-auto px-6 py-4">

      <!-- Search results -->
      <div id="search-results" class="mb-4"></div>

      <!-- Upload -->
      <div class="mb-6 p-4 bg-slate-800 rounded-lg border border-slate-700">
        <div class="text-sm font-semibold text-slate-300 mb-3">Upload Document</div>
        <form id="upload-form" class="flex flex-wrap gap-3 items-end">
          <input type="file" name="file" class="text-sm bg-slate-700 rounded p-2" required>
          <select name="group" id="upload-group" onchange="refreshUploadProjects(this.value)"
                  class="text-sm bg-slate-700 rounded p-2 min-w-[140px]" required>
            <option value="">Select Group</option>
          </select>
          <select name="project" id="upload-project" class="text-sm bg-slate-700 rounded p-2 min-w-[140px]" required>
            <option value="">Select Project</option>
          </select>
          <button type="submit" class="px-4 py-2 bg-green-700 hover:bg-green-600 rounded text-sm">Upload</button>
        </form>
        <div id="upload-msg" class="mt-2 text-xs"></div>
      </div>

      <!-- Document table -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <div class="text-sm font-semibold text-slate-300" id="doc-context">All Documents</div>
          <button onclick="clearFilter()" id="clear-filter-btn" class="hidden text-xs text-slate-500 hover:text-white">✕ Clear filter</button>
        </div>
        <div id="documents"></div>
      </div>
    </div>
  </div>
</div>

<!-- Modal: Add Group -->
<div id="group-modal" class="modal">
  <div class="bg-slate-800 rounded-lg p-6 w-80 border border-slate-600">
    <h3 class="text-lg font-bold mb-4">New Group</h3>
    <input id="new-group-name" class="w-full p-2 bg-slate-700 rounded mb-4 text-sm" placeholder="Group name">
    <div class="flex gap-2 justify-end">
      <button onclick="closeModal('group-modal')" class="px-4 py-2 bg-slate-600 rounded text-sm">Cancel</button>
      <button onclick="createGroup()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded text-sm">Create</button>
    </div>
  </div>
</div>

<!-- Modal: Add Project -->
<div id="project-modal" class="modal">
  <div class="bg-slate-800 rounded-lg p-6 w-80 border border-slate-600">
    <h3 class="text-lg font-bold mb-1">New Project</h3>
    <p class="text-sm text-slate-400 mb-4">In group: <span id="project-modal-group" class="text-indigo-300 font-semibold"></span></p>
    <input id="new-project-name" class="w-full p-2 bg-slate-700 rounded mb-4 text-sm" placeholder="Project name">
    <div class="flex gap-2 justify-end">
      <button onclick="closeModal('project-modal')" class="px-4 py-2 bg-slate-600 rounded text-sm">Cancel</button>
      <button onclick="createProject()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded text-sm">Create</button>
    </div>
  </div>
</div>

<script>
let currentGroup = '';
let currentProject = '';
let allGroups = [];

function openModal(id) {
  if (id === 'project-modal') {
    if (!currentGroup) { alert('Select a group first'); return; }
    document.getElementById('project-modal-group').textContent = currentGroup;
    document.getElementById('new-project-name').value = '';
  }
  if (id === 'group-modal') document.getElementById('new-group-name').value = '';
  document.getElementById(id).classList.add('open');
}
function closeModal(id) { document.getElementById(id).classList.remove('open'); }

async function createGroup() {
  const name = document.getElementById('new-group-name').value.trim();
  if (!name) return;
  await fetch('/api/groups', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name})});
  closeModal('group-modal');
  await refreshAll();
}
async function createProject() {
  const name = document.getElementById('new-project-name').value.trim();
  if (!name) return;
  await fetch('/api/projects', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({group: currentGroup, name})});
  closeModal('project-modal');
  await refreshAll();
}

async function refreshAll() {
  const res = await fetch('/api/groups');
  allGroups = await res.json();
  renderSidebar();
  refreshUploadGroups();
  if (currentGroup) refreshUploadProjects(document.getElementById('upload-group').value);
  loadDocuments();
  loadStats();
}

function renderSidebar() {
  const tree = document.getElementById('sidebar-tree');
  if (!allGroups.length) {
    tree.innerHTML = '<div class="px-4 py-6 text-slate-500 text-sm text-center">No groups yet.<br>Click + to create one.</div>';
    return;
  }
  let html = '';
  for (const g of allGroups) {
    const gActive = currentGroup === g.group_name;
    html += `<div class="sidebar-group mb-1 mx-3 rounded ${gActive ? 'active bg-slate-700' : ''}">
      <div class="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-slate-700 rounded"
           onclick="filterGroup('${esc(g.group_name)}')">
        <span class="text-sm">${gActive ? '▾' : '▸'}</span>
        <span class="text-sm font-semibold ${gActive ? 'text-indigo-300' : 'text-slate-200'}">${esc(g.group_name)}</span>
        <span class="ml-auto text-xs text-slate-500">${g.projects.length}</span>
      </div>`;
    if (gActive && g.projects.length) {
      for (const p of g.projects) {
        const pActive = currentProject === p;
        html += `<div class="sidebar-project px-5 py-1 text-sm cursor-pointer hover:text-indigo-400 ${pActive ? 'active' : 'text-slate-400'}"
                      onclick="filterProject('${esc(g.group_name)}', '${esc(p)}')">${esc(p)}</div>`;
      }
    } else if (gActive && !g.projects.length) {
      html += `<div class="px-5 py-1 text-xs text-slate-600">No projects yet</div>`;
    }
    html += '</div>';
  }
  tree.innerHTML = html;

  // Show/hide add project bar
  const bar = document.getElementById('add-project-bar');
  if (currentGroup) {
    bar.classList.remove('hidden');
    document.getElementById('add-project-label').textContent = currentGroup;
  } else {
    bar.classList.add('hidden');
  }
}

function esc(s) { return String(s).replace(/'/g, "\\'").replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function filterGroup(g) {
  currentGroup = (currentGroup === g) ? '' : g;
  currentProject = '';
  renderSidebar();
  updateDocContext();
  loadDocuments();
}
function filterProject(g, p) {
  currentGroup = g;
  currentProject = (currentProject === p) ? '' : p;
  renderSidebar();
  updateDocContext();
  loadDocuments();
}
function clearFilter() {
  currentGroup = ''; currentProject = '';
  renderSidebar();
  updateDocContext();
  loadDocuments();
}
function updateDocContext() {
  const ctx = currentProject ? `${currentGroup} / ${currentProject}` : currentGroup || 'All Documents';
  document.getElementById('doc-context').textContent = ctx;
  const btn = document.getElementById('clear-filter-btn');
  if (currentGroup) btn.classList.remove('hidden'); else btn.classList.add('hidden');
}

async function loadStats() {
  const res = await fetch('/api/stats');
  const s = await res.json();
  document.getElementById('stats').innerHTML =
    `<span>Docs: <b class="text-white">${s.doc_count}</b></span>
     <span>Chunks: <b class="text-white">${s.chunk_count}</b></span>
     <span>Haystack: <b class="${s.haystack_ok ? 'text-green-400' : 'text-red-400'}">${s.haystack_ok ? 'OK' : 'DOWN'}</b></span>`;
}

async function loadDocuments() {
  const params = new URLSearchParams();
  if (currentGroup) params.append('group', currentGroup);
  if (currentProject) params.append('project', currentProject);
  const res = await fetch('/api/documents?' + params);
  const docs = await res.json();
  if (!docs.length) {
    document.getElementById('documents').innerHTML = '<div class="text-slate-500 text-sm py-4">No documents found.</div>';
    return;
  }
  let html = '<table class="w-full text-sm"><thead><tr class="text-slate-400 text-xs uppercase border-b border-slate-700">'
    + '<th class="pb-2 text-left">Filename</th><th class="pb-2 text-left">Group</th>'
    + '<th class="pb-2 text-left">Project</th><th class="pb-2 text-center">Chunks</th>'
    + '<th class="pb-2 text-left">Date</th><th class="pb-2 text-center">Actions</th>'
    + '</tr></thead><tbody>';
  for (const d of docs) {
    html += `<tr class="border-b border-slate-800 hover:bg-slate-800">
      <td class="py-2 pr-4 font-mono text-xs">${esc(d.filename)}</td>
      <td class="py-2 pr-4"><span class="bg-indigo-900 text-indigo-300 text-xs px-2 py-0.5 rounded">${esc(d.group_name)}</span></td>
      <td class="py-2 pr-4 text-slate-300">${esc(d.project_name)}</td>
      <td class="py-2 text-center text-slate-400">${d.chunks}</td>
      <td class="py-2 pr-4 text-slate-500 text-xs">${new Date(d.created_at).toLocaleDateString()}</td>
      <td class="py-2 text-center">
        <button onclick="deleteDoc(${d.id})" class="mr-2 px-2 py-1 bg-red-900 hover:bg-red-700 text-red-300 rounded text-xs">Delete</button>
        <button onclick="moveDoc(${d.id})" class="px-2 py-1 bg-slate-700 hover:bg-slate-600 rounded text-xs">Move</button>
      </td>
    </tr>`;
  }
  html += '</tbody></table>';
  document.getElementById('documents').innerHTML = html;
}

async function doSearch() {
  const query = document.getElementById('search-query').value.trim();
  if (!query) return;
  const res = await fetch('/api/search', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({query, group: currentGroup, project: currentProject, top_k: 10})
  });
  const results = await res.json();
  if (!results.length) {
    document.getElementById('search-results').innerHTML = '<div class="text-slate-500 text-sm mb-4">No results.</div>';
    return;
  }
  let html = '<div class="mb-4"><div class="text-sm font-semibold text-slate-300 mb-2">Search Results</div>';
  for (const r of results) {
    const score = typeof r.score === 'number' ? r.score.toFixed(3) : '—';
    html += `<div class="mb-2 p-3 bg-slate-800 rounded border border-slate-700 text-sm">
      <div class="flex gap-3 text-xs text-slate-500 mb-1">
        <span>score: <b class="text-indigo-300">${score}</b></span>
        ${r.meta?.group ? `<span>group: ${esc(r.meta.group)}</span>` : ''}
        ${r.meta?.project ? `<span>project: ${esc(r.meta.project)}</span>` : ''}
        ${r.meta?.filename ? `<span>${esc(r.meta.filename)}</span>` : ''}
      </div>
      <div class="text-slate-300">${esc(r.content||'')}</div>
    </div>`;
  }
  html += '</div>';
  document.getElementById('search-results').innerHTML = html;
}
function clearSearch() {
  document.getElementById('search-query').value = '';
  document.getElementById('search-results').innerHTML = '';
}

function refreshUploadGroups() {
  const sel = document.getElementById('upload-group');
  const cur = sel.value;
  let html = '<option value="">Select Group</option>';
  for (const g of allGroups) html += `<option value="${esc(g.group_name)}" ${cur===g.group_name?'selected':''}>${esc(g.group_name)}</option>`;
  sel.innerHTML = html;
}
function refreshUploadProjects(group) {
  const sel = document.getElementById('upload-project');
  if (!group) { sel.innerHTML = '<option value="">Select Project</option>'; return; }
  const g = allGroups.find(x => x.group_name === group);
  let html = '<option value="">Select Project</option>';
  if (g) for (const p of g.projects) html += `<option value="${esc(p)}">${esc(p)}</option>`;
  sel.innerHTML = html;
}

async function deleteDoc(id) {
  if (!confirm('Delete this document and all its chunks?')) return;
  await fetch('/api/documents/' + id, {method: 'DELETE'});
  refreshAll();
}
async function moveDoc(id) {
  const toGroup = prompt('Move to Group:');
  if (!toGroup) return;
  const toProject = prompt('Move to Project:');
  if (!toProject) return;
  await fetch('/api/documents/' + id + '/move', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({to_group: toGroup, to_project: toProject})
  });
  refreshAll();
}

document.getElementById('upload-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = document.getElementById('upload-msg');
  msg.textContent = 'Uploading…';
  msg.className = 'mt-2 text-xs text-yellow-400';
  const formData = new FormData(e.target);
  const res = await fetch('/api/upload', {method: 'POST', body: formData});
  if (res.ok) {
    msg.textContent = 'Upload successful!';
    msg.className = 'mt-2 text-xs text-green-400';
    e.target.reset();
    refreshAll();
  } else {
    const err = await res.json().catch(()=>({}));
    msg.textContent = 'Upload failed: ' + (err.detail || res.status);
    msg.className = 'mt-2 text-xs text-red-400';
  }
});

// Close modals on backdrop click
document.querySelectorAll('.modal').forEach(m => m.addEventListener('click', e => { if (e.target === m) m.classList.remove('open'); }));

refreshAll();
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

@app.post("/login", response_class=HTMLResponse)
def login(username: str = Form(...), password: str = Form(...)):
    if username == config['username'] and bcrypt.checkpw(password.encode(), config['password_hash'].encode()):
        token = serializer.dumps(username)
        resp = HTMLResponse(content=dashboard_html())
        resp.set_cookie('session', token, httponly=False, samesite='lax', path='/')
        return resp
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

@app.post("/api/groups")
def api_create_group(body: dict):
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(400, "Group name required")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO rag_groups (group_name) VALUES (%s) ON CONFLICT DO NOTHING", (name,))
            conn.commit()
    return {"status": "ok"}

@app.post("/api/projects")
def api_create_project(body: dict):
    group = body.get("group", "").strip()
    name = body.get("name", "").strip()
    if not group or not name:
        raise HTTPException(400, "Group and project name required")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM rag_groups WHERE group_name = %s", (group,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Group not found")
            cur.execute("INSERT INTO rag_projects (project_name, group_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (name, row["id"]))
            conn.commit()
    return {"status": "ok"}

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