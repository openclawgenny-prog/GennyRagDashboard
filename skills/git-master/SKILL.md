# Git Master Skill

**Provided Agent:** `git-master`

**When to use:**
- Creating pull requests and managing branches
- Designing or debugging GitHub Actions workflows
- Analyzing commit history and generating changelogs
- Repository setup and configuration
- CI/CD pipeline automation
- Merge strategies and rebasing

**Usage:**
```python
sessions_spawn(
    runtime="subagent",
    agentId="git-master",
    task="Create a GitHub Actions workflow that builds Docker images on push to main"
)
```

**Output:** Git commands, CI YAML configs, PR summaries, and delegation to tester-debugger for validation.

**Model:** `github-copilot/grok-code-fast-1` (primary)

**Delegation:** For code testing and validation, git-master will spawn tester-debugger automatically.
