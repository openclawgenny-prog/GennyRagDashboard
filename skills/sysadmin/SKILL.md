# Sysadmin Skill

**Provided Agent:** `sysadmin`

**When to use:**
- Ubuntu/Linux server health checks and monitoring
- Security hardening and firewall configuration
- Performance tuning and resource optimization
- System troubleshooting and diagnostics
- Backup and restore operations
- Docker container management and debugging
- Log analysis and issue diagnosis

**Usage:**
```python
sessions_spawn(
    runtime="subagent",
    agentId="sysadmin",
    task="Diagnose high CPU usage on Ubuntu ARM64 server and optimize Docker containers"
)
```

**Output:**
1. Diagnosis steps (numbered checklist)
2. Bash scripts/commands to execute
3. Prevention and verification steps
4. Delegation to coding-engineer if application code is needed

**Model:** `github-copilot/gpt-4o` (primary)

**Specialization:** Ubuntu ARM64, general Linux, Docker operations, security, performance.
