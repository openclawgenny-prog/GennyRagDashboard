# docker-orchestrator skill

Purpose
- Manage Docker-based service projects stored under workspace/services/
- Push service projects into the Git repository: https://github.com/openclawgenny-prog/MasterOfCOntainers/
- Ensure GitHub Actions workflow builds images automatically on push
- Monitor GitHub Actions build runs and report status
- On success: tell Portainer to pull the new image and start the container
- Monitor container stats and retrieve logs from Portainer on demand

**When to use:**
- Deploying a service end-to-end (scaffold → push → build → deploy)
- Building and pushing Docker images via GitHub Actions
- Managing service projects in workspace/services/
- Pulling images and starting containers in Portainer
- Monitoring container health and logs

**Usage (via exec):**
```bash
cd workspace/skills/docker-orchestrator
python agent.py deploy myservice --port 8080:8080
```

**Usage (from main agent):**
```python
exec(command="cd workspace/skills/docker-orchestrator && python agent.py deploy myservice --port 8080:8080")
```

Configuration / credential keys (used with get-credential)
- github.masterofcontainers.token — GitHub personal access token (repo + actions scopes)
- registry.masterofcontainers — registry credential payload (username/password or token)
- portainer.url — Portainer base URL (e.g. https://portainer.example.com)
- portainer.api.token — Portainer API token

Workspace layout
- workspace/services/<service-name>/  — service project directories (Dockerfile + code)
- workspace/skills/docker-orchestrator/ — this skill code and templates

Primary capabilities
- scaffold_service(name): create a template service under workspace/services/<name>
- push_service(name, commit_message): commit & push the service into the MasterOfCOntainers repo; returns GitHub Actions run_id
- ensure_workflow(repo_path): place a GitHub Actions workflow that builds the image on push (detects changed services, builds only those)
- monitor_build(owner, repo, run_id): poll GitHub Actions run; returns dict with success status and image_tag on success
- deploy_service(name, commit_message, endpoint_id, ports): full end-to-end orchestration (push → monitor → pull → start → report)
- portainer_pull_image(image_tag, endpoint_id): call Portainer to pull image on the configured endpoint; raises on failure
- portainer_start_container(image_tag, container_name, endpoint_id, ports): create/start the container; raises on failure
- container_stats(container_id): query Portainer for container stats and return them
- container_logs(container_id, tail, endpoint_id): fetch container logs

Usage examples
- python agent.py scaffold my-service
- python agent.py deploy my-service --port 8080:8080
- python agent.py push my-service "Add my-service"  # returns run_id
- python agent.py monitor --owner openclawgenny-prog --repo MasterOfCOntainers --run 123456  # returns image_tag
- python agent.py stats <container_id>
- python agent.py logs <container_id> --tail 100

Contact
- Update SKILL.md in workspace/skills/docker-orchestrator/ to change behavior or add new actions.
