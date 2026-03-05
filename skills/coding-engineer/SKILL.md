# Coding Engineer Skill

**Provided Agent:** `coding-engineer`

**When to use:**
- Writing Python, Bash, or Docker code (>50 lines)
- Debugging scripts or Dockerfiles
- Multi-stage Docker builds (especially OpenClaw/Ollama)
- Any implementation task requiring code
- Iterative bug fixing and error correction

**Usage:**
```python
sessions_spawn(
    runtime="subagent",
    agentId="coding-engineer",
    task="Build a multi-stage Dockerfile for Python FastAPI app with ARM64 support"
)
```

**Output:** Pure code with minimal explanation. Iterates on errors automatically.

**Model:** `github-copilot/grok-code-fast-1` (primary)
