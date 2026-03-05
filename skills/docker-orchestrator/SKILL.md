---
name: docker-orchestrator
description: Build Docker images from Project/DockerImages/, push them to GitHub Container Registry (GHCR), and deploy to a Portainer-managed endpoint. Use when you need to: (1) build one or many images found under Project/DockerImages/, (2) publish images to ghcr.io/<owner>/<repo>/<image>:<tag>, and (3) create or update a Portainer stack that uses those images.
---

# docker-orchestrator

This skill automates a common developer flow: build Docker images from a repository subfolder, push them to GHCR, and deploy or update a stack in Portainer.

Included resources
- scripts/build_and_push.sh — Build and push images found under Project/DockerImages/
- scripts/deploy_portainer.sh — Create or update a Portainer stack (Docker Compose string) that references the pushed images

Default Portainer API URL: http://localhost:9000 (overridable at runtime)

When to use this skill
- You have one or more image folders under Project/DockerImages/, each containing a Dockerfile and (optionally) a context
- You want images published to GitHub Container Registry (ghcr.io) under a GitHub owner/repo namespace
- You want Portainer to run or update a stack that uses those images

Security and secrets
- Credentials are required but never stored in this skill. Provide them via environment variables, your CI secrets, or the OpenClaw credential registry (preferred):
  - GHCR_USER (GitHub username or ghcr user)
  - GHCR_PAT (GitHub Personal Access Token with write:packages and read:packages; use GITHUB_TOKEN in GitHub Actions)
  - GITHUB_OWNER (owner or org for the GHCR namespace)
  - GITHUB_REPO (repository name used in image namespace)
  - PORTAINER_URL (e.g. https://portainer.example.com)
  - PORTAINER_TOKEN (Portainer API JWT token)
  - PORTAINER_ENDPOINT_ID (numeric endpoint id in Portainer)

Credential sources and autodetect
- This skill supports multiple credential sources and follows a clear precedence:
  1) Explicit env vars (GHCR_PAT, GHCR_USER, etc.)
  2) --use-credential NAME (fetch from OpenClaw credential registry via get-credential)
  3) --registry-file PATH (explicit registry/config file like ~/.docker/config.json)
  4) --auto-detect (opt-in: try common get-credential names then ~/.docker/config.json)

Usage patterns
1. Build & push all images (recommended for local testing):
   ./scripts/build_and_push.sh --all --tag v1.0.0

2. Build & push a single image:
   ./scripts/build_and_push.sh --path Project/DockerImages/my-service --tag v1.0.0

3. Deploy/update a Portainer stack using a local docker-compose.yml (the script will upload the compose content and create/update the named stack):
   ./scripts/deploy_portainer.sh --stack-name my-stack --compose-file ./deploy/docker-compose.yml

Notes and limitations
- This skill assumes Docker Buildx is available for multi-platform builds and that docker CLI is logged out/in for GHCR as shown in scripts.
- For CI, pass GHCR credentials via environment variables or GitHub Actions secrets (GITHUB_TOKEN can be used for GHCR in the same repo when permissions allow).
- Portainer API versions differ slightly between releases; the provided deploy script uses the common stack create/update endpoints (method=string). If your Portainer is heavily customized, adjust the script accordingly.

If you want, I can:
- Run the scripts locally (I will ask for credentials and confirmation first)
- Adapt the scripts into GitHub Actions workflow files
- Validate a sample Project/DockerImages/ layout and produce a dry-run report
- Add auto-detect support (the build script now supports --use-credential and --auto-detect to find GHCR credentials from the OpenClaw registry or ~/.docker/config.json)
