#!/usr/bin/env python3
"""
Get credential from OpenClaw credential registry.

Usage:
    python get-credential.py <logical_name>

Returns the credential token as plain text to stdout.
Logs access to ~/.openclaw/credentials/access.log
"""
import sys
import json
from pathlib import Path
from datetime import datetime

REGISTRY_PATH = Path.home() / '.openclaw' / 'credentials' / 'registry.json'
LOG_PATH = Path.home() / '.openclaw' / 'credentials' / 'access.log'

# Mapping of logical names used by docker-orchestrator to registry keys
CREDENTIAL_MAP = {
    'github.masterofcontainers.token': 'git_full_access',
    'portainer.api.token': 'portainer_api',
    'portainer.url': None,  # Not in registry, will use default
}

def get_credential(logical_name):
    """Fetch credential from registry by logical name."""
    
    # Special case: portainer.url is not a secret, return default
    if logical_name == 'portainer.url':
        return 'http://127.0.0.1:9000'
    
    # Map logical name to registry key
    registry_key = CREDENTIAL_MAP.get(logical_name, logical_name)
    
    if not REGISTRY_PATH.exists():
        print(f"Error: Registry not found at {REGISTRY_PATH}", file=sys.stderr)
        sys.exit(1)
    
    with open(REGISTRY_PATH) as f:
        registry = json.load(f)
    
    if registry_key not in registry:
        print(f"Error: Credential '{registry_key}' not found in registry", file=sys.stderr)
        sys.exit(1)
    
    credential = registry[registry_key]
    token = credential.get('token')
    
    if not token:
        print(f"Error: No token field in credential '{registry_key}'", file=sys.stderr)
        sys.exit(1)
    
    # Log access
    log_access(logical_name, registry_key)
    
    return token


def log_access(logical_name, registry_key):
    """Log credential access for audit trail."""
    timestamp = datetime.now().isoformat()
    log_entry = f"[{timestamp}] Accessed: {registry_key} (requested as: {logical_name})\n"
    
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, 'a') as f:
        f.write(log_entry)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python get-credential.py <logical_name>", file=sys.stderr)
        sys.exit(1)
    
    logical_name = sys.argv[1]
    token = get_credential(logical_name)
    print(token)
