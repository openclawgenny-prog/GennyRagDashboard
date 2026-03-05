docker-orchestrator

Quick start

1. **Install dependencies:**
   ```bash
   cd workspace/skills/docker-orchestrator
   pip install -r requirements.txt
   ```

2. **Set up credentials** (choose one method):
   - Via get-credential skill (recommended): store credentials using your credential registry
   - Via environment variables:
     - GITHUB_MASTEROFCONTAINERS_TOKEN
     - PORTAINER_URL
     - PORTAINER_API_TOKEN
   - Via local credentials.json file in this skill folder

3. **Scaffold a new service:**
   ```bash
   python agent.py scaffold myservice
   ```

4. **Implement your app** in workspace/services/myservice/ (edit app.py and Dockerfile)

5. **Deploy end-to-end** (push → build → pull → start):
   ```bash
   python agent.py deploy myservice --port 8080:8080
   ```

   This single command:
   - Pushes code to GitHub (openclawgenny-prog/MasterOfCOntainers)
   - Waits for GitHub Actions to build the image
   - Tells Portainer to pull the new image
   - Starts the container
   - Reports container stats

Manual workflow (if you prefer step-by-step):

1. Push service:
   ```bash
   python agent.py push myservice "Add myservice"
   # Returns: GitHub Actions run ID
   ```

2. Monitor build:
   ```bash
   python agent.py monitor --owner openclawgenny-prog --repo MasterOfCOntainers --run 123456
   # Returns: built image tag
   ```

3. Pull and start container:
   ```bash
   python agent.py pull-and-start ghcr.io/openclawgenny-prog/masterofcontainers/myservice:abc1234 myservice
   ```

4. Check container stats:
   ```bash
   python agent.py stats <container_id>
   ```

5. View logs:
   ```bash
   python agent.py logs <container_id> --tail 100
   ```

Notes
- The GitHub Actions workflow (auto-installed on first push) builds and pushes images to ghcr.io using the repo's GITHUB_TOKEN
- Images are tagged with both the git SHA and 'latest'
- The workflow detects which service changed and only builds that service
- Portainer endpoint ID defaults to 1 (use --endpoint-id to override)
- Port mappings use Docker format: <container_port>:<host_port>

