# Credentials index (auto-generated)
This file lists credential files present in ~/.openclaw/credentials and a suggested purpose for each. Tokens are masked; do NOT store extra copies in plaintext elsewhere.

- portainer.json: Portainer API key (use for Portainer API calls)
  masked: ptr_KI...0R4=
- github-copilot.token.json: GitHub Copilot token (editor integration)
  masked: tid=27...bd8a
- telegram-default-allowFrom.json: Telegram pairing/allowlist tokens
  masked: None

Best practices:
- Use descriptive names: github_master_pat.json, ghcr_push_pat.json, portainer_api.json.
- Store minimal scopes for tokens (least privilege).
- Set file permissions to 600: chmod 600 ~/.openclaw/credentials/*.
- Reference credentials by logical name in code (do not hardcode filenames).
- Rotate tokens periodically and update metadata in registry.json