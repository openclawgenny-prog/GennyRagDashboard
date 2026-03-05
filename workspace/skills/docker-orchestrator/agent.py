#!/usr/bin/env python3
"""
docker-orchestrator agent

Usage (CLI):
  agent.py scaffold <service_name>
  agent.py push <service_name> [<commit_message>]
  agent.py deploy <service_name> [--message <msg>] [--endpoint-id <id>] [--port 8080:8080]
  agent.py monitor --owner <owner> --repo <repo> --run <run_id>
  agent.py pull-and-start <image_tag> <container_name> [--endpoint-id <id>]
  agent.py stats <container_id>
  agent.py logs <container_id> [--tail <n>]

New: 'deploy' command orchestrates the full workflow:
  scaffold → push → monitor → pull → start → report
"""
import os
import sys
import time
import json
import subprocess
from pathlib import Path
import requests

WORKSPACE = Path(os.environ.get('HOME', '.')) / '.openclaw' if False else Path.cwd()
SERVICES_DIR = WORKSPACE / 'services'
SKILL_DIR = Path(__file__).parent
LOG_FILE = SKILL_DIR / 'logs.txt'

GITHUB_REPO = 'openclawgenny-prog/MasterOfCOntainers'
GITHUB_API = 'https://api.github.com'

# Helper logging
def log(msg):
    LINE = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
    print(LINE, end='')
    with open(LOG_FILE, 'a') as f:
        f.write(LINE)

# Credential helpers (integrated with get-credential skill when available)
def get_cred(key):
    # 1) check environment variables (convert dots to underscores)
    env_key = key.upper().replace('.', '_')
    v = os.environ.get(env_key)
    if v:
        return v

    # 2) try to call the workspace get-credential.py script (if present)
    possible_paths = [
        Path.home() / '.openclaw' / 'workspace' / 'credentials' / 'get-credential.py',
        SKILL_DIR.parent.parent / 'credentials' / 'get-credential.py',
        SKILL_DIR.parent / 'get-credential' / 'get_credential.py',
        SKILL_DIR.parent / 'get-credential' / 'get-credential.py',
    ]
    for p in possible_paths:
        if p.exists():
            try:
                out = subprocess.run(['python3', str(p), key], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if out.returncode == 0 and out.stdout:
                    # try to parse JSON output, otherwise return raw text
                    txt = out.stdout.strip()
                    try:
                        return json.loads(txt)
                    except Exception:
                        return txt
            except Exception as e:
                log(f'get_credential call failed: {e}')

    # 3) fallback: try a local credentials.json in this skill folder
    cred_file = SKILL_DIR / 'credentials.json'
    if cred_file.exists():
        data = json.loads(cred_file.read_text())
        return data.get(key)

    return None

# Git helpers

def ensure_services_dir():
    SERVICES_DIR.mkdir(parents=True, exist_ok=True)


def scaffold_service(name):
    ensure_services_dir()
    sdir = SERVICES_DIR / name
    sdir.mkdir(exist_ok=True)
    # create a simple app and Dockerfile
    app_py = sdir / 'app.py'
    dockerfile = sdir / 'Dockerfile'
    readme = sdir / 'README.md'
    if not app_py.exists():
        app_py.write_text("""from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type','text/plain')
        self.end_headers()
        self.wfile.write(b'Hello from %s' )

if __name__=='__main__':
    server = HTTPServer(('0.0.0.0', 8080), Handler)
    print('Listening on 8080')
    server.serve_forever()
""")
    if not dockerfile.exists():
        dockerfile.write_text("""FROM python:3.11-slim
WORKDIR /app
COPY . /app
EXPOSE 8080
CMD ["python", "app.py"]
""")
    if not readme.exists():
        readme.write_text(f"# {name}\n\nSample service {name}\n")
    log(f"Scaffolded service {name} at {sdir}")

# Push service: create a temporary clone of the target repo, copy the service folder, commit and push

def run(cmd, cwd=None, check=True):
    log(f"$ {' '.join(cmd)} (cwd={cwd})")
    r = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if r.returncode != 0 and check:
        log(r.stdout)
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return r.stdout


def push_service(name, commit_message='Add service via docker-orchestrator'):
    token = get_cred('github.masterofcontainers.token')
    if not token:
        raise RuntimeError('Missing github.masterofcontainers.token credential')
    tmp = SKILL_DIR / 'tmp_repo'
    if tmp.exists():
        subprocess.run(['rm', '-rf', str(tmp)])
    repo_url = f'https://{token}:x-oauth-basic@github.com/{GITHUB_REPO}.git'
    run(['git', 'clone', repo_url, str(tmp)])
    # ensure workflow exists
    ensure_workflow(tmp)
    src = SERVICES_DIR / name
    if not src.exists():
        raise RuntimeError(f'service {name} not found under services/')
    dest = tmp / name
    if dest.exists():
        subprocess.run(['rm', '-rf', str(dest)])
    run(['cp', '-r', str(src), str(dest)])
    run(['git', 'add', '.'], cwd=str(tmp))
    run(['git', 'commit', '-m', commit_message], cwd=str(tmp))
    run(['git', 'push', 'origin', 'HEAD:main'], cwd=str(tmp))
    log(f'Pushed service {name} to {GITHUB_REPO}')
    
    # Get the latest workflow run ID for this push
    run_id = get_latest_run_id(GITHUB_REPO.split('/')[0], GITHUB_REPO.split('/')[1], token)
    if run_id:
        log(f'GitHub Actions run started: {run_id}')
    return run_id


def get_latest_run_id(owner, repo, token, max_attempts=5):
    """Fetch the most recent workflow run ID (polls a few times to catch new runs)"""
    headers = {'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'}
    url = f'{GITHUB_API}/repos/{owner}/{repo}/actions/runs?per_page=1'
    for attempt in range(max_attempts):
        time.sleep(2)  # GitHub may take a moment to register the push
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            data = r.json()
            runs = data.get('workflow_runs', [])
            if runs:
                return runs[0]['id']
        log(f'Waiting for workflow run to appear (attempt {attempt+1}/{max_attempts})...')
    log('Warning: could not fetch run ID')
    return None


# Ensure a GitHub Actions workflow that builds docker image exists

def ensure_workflow(repo_path: Path):
    wf_dir = repo_path / '.github' / 'workflows'
    wf_dir.mkdir(parents=True, exist_ok=True)
    wf = wf_dir / 'build-and-push.yml'
    if wf.exists():
        return
    wf.write_text("""name: Build and push containers

on:
  push:
    branches:
      - main
    paths:
      - '*/Dockerfile'
      - '**/*.py'

jobs:
  detect-changes:
    runs-on: ubuntu-latest
    outputs:
      services: ${{ steps.filter.outputs.changes }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v2
        id: filter
        with:
          filters: |
            */Dockerfile

  build:
    needs: detect-changes
    if: needs.detect-changes.outputs.services != '[]'
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service: ${{ fromJSON(needs.detect-changes.outputs.services) }}
    steps:
      - uses: actions/checkout@v4
      - name: Extract service name
        id: service
        run: echo "name=$(echo ${{ matrix.service }} | cut -d'/' -f1)" >> $GITHUB_OUTPUT
      - name: Set up QEMU
        uses: docker/setup-qemu-action@v2
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
      - name: Login to registry
        uses: docker/login-action@v2
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Docker metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}/${{ steps.service.outputs.name }}
          tags: |
            type=sha,prefix=
            type=raw,value=latest
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: ./${{ steps.service.outputs.name }}
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
""")
    log('Installed GitHub Actions workflow build-and-push.yml')

# Monitor GitHub Actions run

def monitor_build(owner, repo, run_id, poll_interval=6):
    token = get_cred('github.masterofcontainers.token')
    if not token:
        raise RuntimeError('Missing github.masterofcontainers.token')
    headers = {'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'}
    url = f'{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}'
    while True:
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            log(f'Failed to fetch run: {r.status_code} {r.text}')
            time.sleep(poll_interval)
            continue
        data = r.json()
        status = data.get('status')
        conclusion = data.get('conclusion')
        log(f'Run status={status} conclusion={conclusion}')
        if status == 'completed':
            if conclusion == 'success':
                log('Build succeeded')
                # Extract image tag from run artifacts/jobs (simplified: use repo + sha)
                sha = data.get('head_sha', 'latest')
                image_tag = f"ghcr.io/{owner}/{repo}:#{sha[:7]}"
                log(f'Built image tag: {image_tag}')
                return {'success': True, 'image_tag': image_tag, 'sha': sha}
            else:
                log('Build failed')
                return {'success': False, 'conclusion': conclusion}
        time.sleep(poll_interval)

# Portainer API helpers

def portainer_headers():
    token = get_cred('portainer.api.token')
    if not token:
        raise RuntimeError('Missing portainer.api.token')
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


def portainer_base():
    url = get_cred('portainer.url')
    if not url:
        raise RuntimeError('Missing portainer.url')
    return url.rstrip('/')


def portainer_pull_image(image, endpoint_id=None):
    base = portainer_base()
    headers = portainer_headers()
    endpoint_id = endpoint_id or 1
    url = f'{base}/api/endpoints/{endpoint_id}/docker/images/create?fromImage={image}'
    r = requests.post(url, headers=headers)
    if r.status_code not in (200, 201, 204):
        log(f'Portainer pull image failed: {r.status_code} {r.text}')
        raise RuntimeError(f'Failed to pull image {image}')
    log(f'Portainer pulled image {image} on endpoint {endpoint_id}')
    return image


def portainer_start_container(image, name, endpoint_id=None, ports=None):
    base = portainer_base()
    headers = portainer_headers()
    endpoint_id = endpoint_id or 1
    
    # Build port bindings if provided (e.g., {"8080/tcp": [{"HostPort": "8080"}]})
    port_bindings = {}
    exposed_ports = {}
    if ports:
        for container_port, host_port in ports.items():
            port_bindings[container_port] = [{"HostPort": str(host_port)}]
            exposed_ports[container_port] = {}
    
    # create container
    url = f'{base}/api/endpoints/{endpoint_id}/docker/containers/create?name={name}'
    payload = {
        'Image': image,
        'ExposedPorts': exposed_ports,
        'HostConfig': {'PortBindings': port_bindings}
    }
    r = requests.post(url, headers=headers, json=payload)
    if r.status_code not in (200,201):
        log(f'Failed to create container: {r.status_code} {r.text}')
        raise RuntimeError(f'Failed to create container {name}')
    cid = r.json().get('Id')
    # start
    url2 = f'{base}/api/endpoints/{endpoint_id}/docker/containers/{cid}/start'
    r2 = requests.post(url2, headers=headers)
    if r2.status_code not in (200,204):
        log(f'Failed to start container: {r2.status_code} {r2.text}')
        raise RuntimeError(f'Failed to start container {cid}')
    log(f'Started container {cid} from image {image}')
    return cid


def container_stats(container_id, endpoint_id=None):
    base = portainer_base()
    headers = portainer_headers()
    endpoint_id = endpoint_id or 1
    url = f'{base}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/stats?stream=false'
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        log(f'Failed to get stats: {r.status_code} {r.text}')
        return None
    return r.json()


def container_logs(container_id, tail=200, endpoint_id=None):
    base = portainer_base()
    headers = portainer_headers()
    endpoint_id = endpoint_id or 1
    url = f'{base}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/logs?stdout=1&stderr=1&tail={tail}'
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        log(f'Failed to get logs: {r.status_code} {r.text}')
        return None
    return r.text

# Deploy orchestration command - full workflow

def deploy_service(name, commit_message='Deploy service via docker-orchestrator', endpoint_id=None, ports=None):
    """Full end-to-end deployment: scaffold → push → monitor → pull → start → report"""
    log(f'=== Starting deployment of {name} ===')
    
    # 1. Push service to GitHub
    log('Step 1: Pushing service to GitHub...')
    run_id = push_service(name, commit_message)
    if not run_id:
        raise RuntimeError('Failed to get GitHub Actions run ID')
    
    # 2. Monitor build
    log(f'Step 2: Monitoring GitHub Actions run {run_id}...')
    owner, repo = GITHUB_REPO.split('/')
    result = monitor_build(owner, repo, run_id)
    
    if not result['success']:
        log(f'Deployment failed: build {result.get("conclusion", "unknown")}')
        return {'success': False, 'stage': 'build', 'result': result}
    
    image_tag = result['image_tag']
    log(f'Build succeeded, image: {image_tag}')
    
    # 3. Pull image in Portainer
    log(f'Step 3: Pulling image {image_tag} in Portainer...')
    try:
        portainer_pull_image(image_tag, endpoint_id)
    except Exception as e:
        log(f'Deployment failed: pull error: {e}')
        return {'success': False, 'stage': 'pull', 'error': str(e)}
    
    # 4. Start container
    log(f'Step 4: Starting container {name}...')
    try:
        container_id = portainer_start_container(image_tag, name, endpoint_id, ports)
    except Exception as e:
        log(f'Deployment failed: start error: {e}')
        return {'success': False, 'stage': 'start', 'error': str(e)}
    
    # 5. Get stats
    log(f'Step 5: Fetching container stats...')
    stats = container_stats(container_id, endpoint_id)
    
    log(f'=== Deployment successful ===')
    log(f'Container ID: {container_id}')
    log(f'Image: {image_tag}')
    
    return {
        'success': True,
        'container_id': container_id,
        'image_tag': image_tag,
        'run_id': run_id,
        'stats': stats
    }


# CLI entrypoint

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'scaffold':
        scaffold_service(sys.argv[2])
    elif cmd == 'push':
        name = sys.argv[2]
        msg = sys.argv[3] if len(sys.argv) > 3 else 'Add service via docker-orchestrator'
        run_id = push_service(name, msg)
        if run_id:
            print(f'Pushed. GitHub Actions run ID: {run_id}')
        else:
            print('Pushed, but could not fetch run ID')
    elif cmd == 'monitor':
        import argparse
        p = argparse.ArgumentParser()
        p.add_argument('--owner', required=True)
        p.add_argument('--repo', required=True)
        p.add_argument('--run', required=True, type=int)
        args = p.parse_args(sys.argv[2:])
        result = monitor_build(args.owner, args.repo, args.run)
        if not result['success']:
            log(f'Reporting: build failed ({result.get("conclusion")})')
            sys.exit(2)
        else:
            log(f'Reporting: build succeeded, image={result["image_tag"]}')
            print(result['image_tag'])
            sys.exit(0)
    elif cmd == 'deploy':
        import argparse
        p = argparse.ArgumentParser()
        p.add_argument('service', help='Service name')
        p.add_argument('--message', default='Deploy via docker-orchestrator', help='Commit message')
        p.add_argument('--endpoint-id', type=int, default=None, help='Portainer endpoint ID')
        p.add_argument('--port', action='append', help='Port mapping (format: 8080:8080)')
        args = p.parse_args(sys.argv[2:])
        
        ports = None
        if args.port:
            ports = {}
            for mapping in args.port:
                container, host = mapping.split(':')
                ports[f'{container}/tcp'] = host
        
        result = deploy_service(args.service, args.message, args.endpoint_id, ports)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result['success'] else 1)
    elif cmd == 'pull-and-start':
        image = sys.argv[2]
        name = sys.argv[3]
        try:
            portainer_pull_image(image)
            container_id = portainer_start_container(image, name)
            print(f'Started container {container_id}')
        except Exception as e:
            log(f'Error: {e}')
            sys.exit(1)
    elif cmd == 'stats':
        cid = sys.argv[2]
        s = container_stats(cid)
        print(json.dumps(s, indent=2))
    elif cmd == 'logs':
        cid = sys.argv[2]
        tail = 200
        if '--tail' in sys.argv:
            tail = int(sys.argv[sys.argv.index('--tail')+1])
        print(container_logs(cid, tail=tail))
    else:
        print('Unknown command', cmd)

if __name__ == '__main__':
    main()
