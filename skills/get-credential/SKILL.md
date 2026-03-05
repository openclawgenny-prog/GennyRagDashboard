---
name: get-credential
description: Skill to efficiently retrieve credentials stored in the OpenClaw credential registry using `get_credential.py`. Handles access requests by logical name with secure output options.
---

# Get Credential Skill

This skill provides an interface for retrieving credentials stored in the OpenClaw credential management system. It leverages the `get_credential.py` script to fetch tokens and metadata based on logical credential names defined in `registry.json`.

## Usage

1. **Retrieve a credential by logical name:**
   ```bash
   python get_credential.py <logical_name>
   ```
   - Example: `python get_credential.py portainer_api`
   - Output includes the masked token and metadata.

2. **Integrate into workflows:**
   - Use logical credential names in scripts, avoiding hard-coding sensitive information.
   - Access audit trail in `cred_access.log`.


## Notes

- Ensure the `registry.json` file is up-to-date.
- Follow least privilege principles when assigning scopes to tokens.