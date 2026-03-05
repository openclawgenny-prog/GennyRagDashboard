# Solution Architect Skill

**Provided Agent:** `solution-architect`

**When to use:**
- Designing system architecture for new projects
- Multi-component deployments (Docker, Portainer, microservices)
- Infrastructure planning and scalability design
- High-level system diagrams (Mermaid/ASCII)
- DevOps pipeline architecture
- Questions starting with "How should I architect..."

**Usage:**
```python
sessions_spawn(
    runtime="subagent",
    agentId="solution-architect",
    task="Design a scalable architecture for running 5 Ollama models behind a load balancer on ARM64"
)
```

**Output:**
1. High-level architecture diagram (Mermaid)
2. Component breakdown with descriptions
3. Deployment artifacts (docker-compose.yml, configs)
4. Risk assessment and mitigation strategies

**Model:** `github-copilot/gpt-4o` (primary)

**Delegation:** For implementation code, solution-architect will spawn coding-engineer automatically.
