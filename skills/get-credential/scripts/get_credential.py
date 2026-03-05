import json
import os
from pathlib import Path

REGISTRY_PATH = Path.home() / '.openclaw' / 'credentials' / 'registry.json'
CRED_DIR = Path.home() / '.openclaw' / 'credentials'
AUDIT_LOG = Path.home() / '.openclaw' / 'master_logs' / 'cred_access.log'


def _find_token_in_obj(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and len(v) > 20 and any(x in k.lower() for x in ('token', 'pat', 'key', 'auth')):
                return v
            if isinstance(v, dict):
                res = _find_token_in_obj(v)
                if res:
                    return res
    return None


def get_credential(logical_name):
    """Return (token, metadata) for the given logical credential name.

    The manifest ~/.openclaw/credentials/registry.json maps logical names to filenames and metadata.
    Prefer the token stored in the manifest (registry.json) under the entry['token'] field; if absent,
    fall back to reading the mapped credential file and extracting a token-like field.

    It appends an audit line into ~/.openclaw/master_logs/cred_access.log recording access (no token content).
    """
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f'Registry manifest not found at {REGISTRY_PATH}')
    reg = json.load(open(REGISTRY_PATH))
    entry = reg.get(logical_name)
    if not entry:
        raise KeyError(f'Credential "{logical_name}" not found in registry manifest')
    # Require token embedded in manifest (registry.json is the single source of truth).
    token = entry.get('token')
    if not token:
        raise ValueError(f'Credential "{logical_name}" does not have a token in registry.json.\nPlease add the token value to registry.json under the entry["token"] field before calling get_credential.')
    meta = dict(entry)
    meta['file_path'] = str(CRED_DIR / entry.get('file')) if entry.get('file') else None
    # audit
    try:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG, 'a') as f:
            f.write(f"{__import__('datetime').datetime.utcnow().isoformat()}Z\t{logical_name}\tpid={os.getpid()}\tuser={os.getenv('USER','unknown')}\n")
    except Exception:
        pass
    return token, meta


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Usage: get_credential.py <logical_name>')
        raise SystemExit(2)
    name = sys.argv[1]
    t, m = get_credential(name)
    print('MASKED:', (t[:6] + '...' + t[-4:]) if t else None)
    print(json.dumps(m, indent=2))
