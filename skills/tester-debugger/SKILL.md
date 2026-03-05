# Tester Debugger Skill

**Provided Agent:** `tester-debugger`

**When to use:**
- Running unit, integration, or end-to-end tests
- Finding and reproducing bugs in code
- Validating Docker image integrity
- Security vulnerability scanning
- Code quality validation and coverage reporting
- Root cause analysis for production issues
- Creating proof-of-concept bug reproductions

**Usage:**
```python
sessions_spawn(
    runtime="subagent",
    agentId="tester-debugger",
    task="Run tests on the FastAPI service and identify any failing test cases"
)
```

**Output:**
1. Test plan and PASS/FAIL results
2. Detailed bug list with reproduction steps
3. Proposed fixes (delegates implementation to coding-engineer)
4. Coverage report (if available)

**Model:** `github-copilot/gpt-5.1-codex-max` (primary)

**Delegation:** For implementing bug fixes, tester-debugger will spawn coding-engineer automatically.
