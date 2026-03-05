#!/usr/bin/env bash
set -euo pipefail

# build_and_push.sh
# Build Docker images found under Project/DockerImages/ and push to GHCR

usage() {
  cat <<EOF
Usage: $0 [--all] [--path PATH] --tag TAG [--no-push] [--platforms PLATFORMS]
           [--use-credential NAME] [--registry-file PATH] [--auto-detect]

Options:
  --all                 Build all images found under Project/DockerImages/
  --path PATH           Build only the image at PATH (must contain a Dockerfile)
  --tag TAG             Tag to apply (required)
  --push / --no-push    Push images to ghcr.io (default: push)
  --platforms PLATFORMS Comma-separated platforms for buildx (default: linux/amd64)
  --use-credential NAME Use OpenClaw get-credential logical name to fetch GHCR token
  --registry-file PATH  Parse a registry/config file (e.g. ~/.docker/config.json) for credentials
  --auto-detect         Try common locations (get-credential, ~/.docker/config.json)
EOF
}

ALL=false
PATH_ARG=""
TAG=""
PUSH=true
PLATFORMS="linux/amd64"
USE_CRED_NAME=""
REGISTRY_FILE=""
AUTO_DETECT=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all) ALL=true; shift;;
    --path) PATH_ARG="$2"; shift 2;;
    --tag) TAG="$2"; shift 2;;
    --push) PUSH=true; shift;;
    --no-push) PUSH=false; shift;;
    --platforms) PLATFORMS="$2"; shift 2;;
    --use-credential) USE_CRED_NAME="$2"; shift 2;;
    --registry-file) REGISTRY_FILE="$2"; shift 2;;
    --auto-detect) AUTO_DETECT=true; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

if [[ -z "$TAG" ]]; then
  echo "--tag is required" >&2
  usage
  exit 1
fi

ROOT_DIR="Project/DockerImages"

if [[ "$ALL" = false && -z "$PATH_ARG" ]]; then
  echo "Either --all or --path PATH must be specified" >&2
  usage
  exit 1
fi

images=()
if [[ "$ALL" = true ]]; then
  while IFS= read -r -d $'\0' dir; do
    images+=("$dir")
  done < <(find "$ROOT_DIR" -maxdepth 2 -type f -name Dockerfile -print0 | xargs -0 -n1 dirname -z)
else
  if [[ ! -f "$PATH_ARG/Dockerfile" ]]; then
    echo "Dockerfile not found in $PATH_ARG" >&2
    exit 1
  fi
  images+=("$PATH_ARG")
fi

if [[ ${#images[@]} -eq 0 ]]; then
  echo "No images found under $ROOT_DIR" >&2
  exit 1
fi

# Credential resolution precedence:
# 1) Env vars GHCR_PAT (+ optional GHCR_USER)
# 2) --use-credential NAME (OpenClaw get-credential)
# 3) --registry-file PATH (explicit file)
# 4) --auto-detect (try get-credential common names, then ~/.docker/config.json)

GHCR_USER="${GHCR_USER:-}"
GHCR_PAT="${GHCR_PAT:-}"
GITHUB_OWNER="${GITHUB_OWNER:-}"
GITHUB_REPO="${GITHUB_REPO:-}"

# Helper: fetch token using get_credential Python module (returns token or empty)
get_token_from_get_credential() {
  local name="$1"
  python3 - <<PY 2>/dev/null || true
import importlib.util, sys
spec = importlib.util.spec_from_file_location('gcmod', '${HOME}/.openclaw/workspace/skills/get-credential/scripts/get_credential.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
try:
    token, meta = mod.get_credential('${name}')
    print(token)
except Exception as e:
    sys.exit(2)
PY
}

# Helper: parse docker config file for ghcr.io auth
get_token_from_docker_config() {
  local cfg_path="$1"
  if [[ ! -f "$cfg_path" ]]; then
    return 1
  fi
  local auth_b64
  auth_b64=$(python3 - <<PY 2>/dev/null || true
import json,sys
p='''$cfg_path'''
try:
  cfg=json.load(open(p))
  a=cfg.get('auths',{}).get('ghcr.io',{})
  auth=a.get('auth')
  if auth:
    print(auth)
except Exception:
  sys.exit(1)
PY
)
  if [[ -z "$auth_b64" ]]; then
    return 1
  fi
  # decode
  local creds
  creds=$(echo "$auth_b64" | base64 --decode 2>/dev/null || true)
  if [[ -z "$creds" ]]; then
    return 1
  fi
  GHCR_USER_LOCAL=$(echo "$creds" | cut -d: -f1)
  GHCR_PAT_LOCAL=$(echo "$creds" | cut -d: -f2-)
  echo "${GHCR_USER_LOCAL}:${GHCR_PAT_LOCAL}"
  return 0
}

# Step 1: env vars already read above
if [[ -n "$GHCR_PAT" && -n "$GITHUB_OWNER" && -n "$GITHUB_REPO" ]]; then
  echo "Using GHCR credentials from environment variables (GHCR_PAT + GITHUB_OWNER/GITHUB_REPO)"
else
  # Step 2: use get-credential if requested
  if [[ -n "$USE_CRED_NAME" ]]; then
    echo "Fetching credential '$USE_CRED_NAME' via get-credential"
    token=$(get_token_from_get_credential "$USE_CRED_NAME" ) || true
    if [[ -n "$token" ]]; then
      GHCR_PAT="$token"
      echo "Got token from get-credential (masked: ${token:0:6}...${token: -4})"
    else
      echo "get-credential did not return a token or failed for '$USE_CRED_NAME'" >&2
    fi
  fi
fi

# Step 3: registry file if provided (explicit file)
if [[ -z "$GHCR_PAT" && -n "$REGISTRY_FILE" ]]; then
  echo "Parsing registry file: $REGISTRY_FILE"
  # try docker config format
  out=$(get_token_from_docker_config "$REGISTRY_FILE" ) || true
  if [[ -n "$out" ]]; then
    GHCR_USER=$(echo "$out" | cut -d: -f1)
    GHCR_PAT=$(echo "$out" | cut -d: -f2-)
    echo "Extracted GHCR credentials from $REGISTRY_FILE for user $GHCR_USER"
  else
    echo "No ghcr.io auth found in $REGISTRY_FILE" >&2
  fi
fi

# Step 4: auto-detect
if [[ -z "$GHCR_PAT" && "$AUTO_DETECT" = true ]]; then
  echo "Auto-detect enabled: trying known credential names via get-credential"
  candidates=(ghcr ghcr_pat ghcr_token github_pat github_token packages_token)
  for c in "${candidates[@]}"; do
    token=$(get_token_from_get_credential "$c" ) || true
    if [[ -n "$token" ]]; then
      GHCR_PAT="$token"
      echo "Found token via get-credential name='$c' (masked: ${token:0:6}...${token: -4})"
      break
    fi
  done
  if [[ -z "$GHCR_PAT" ]]; then
    # fallback to Docker config
    echo "Trying ~/.docker/config.json for ghcr.io auth"
    out=$(get_token_from_docker_config "$HOME/.docker/config.json" ) || true
    if [[ -n "$out" ]]; then
      GHCR_USER=$(echo "$out" | cut -d: -f1)
      GHCR_PAT=$(echo "$out" | cut -d: -f2-)
      echo "Extracted GHCR credentials from ~/.docker/config.json for user $GHCR_USER"
    fi
  fi
fi

if [[ -z "$GHCR_PAT" || -z "$GITHUB_OWNER" || -z "$GITHUB_REPO" ]]; then
  echo "Environment variables or credentials missing. Please provide GITHUB_OWNER and GITHUB_REPO and a GHCR token via one of: GHCR_PAT env, --use-credential NAME, --registry-file PATH, or --auto-detect." >&2
  exit 1
fi

# Login to ghcr
LOGIN_USER="${GHCR_USER:-$GITHUB_OWNER}"
if [[ -n "$LOGIN_USER" ]]; then
  echo "Logging in to ghcr.io as $LOGIN_USER"
  echo "$GHCR_PAT" | docker login ghcr.io -u "$LOGIN_USER" --password-stdin
else
  echo "$GHCR_PAT" | docker login ghcr.io -u "$GITHUB_OWNER" --password-stdin
fi

for img_dir in "${images[@]}"; do
  name=$(basename "$img_dir")
  image_ref="ghcr.io/${GITHUB_OWNER}/${GITHUB_REPO}/${name}:${TAG}"
  echo "Building $image_ref from $img_dir"
  docker buildx build --platform "$PLATFORMS" -t "$image_ref" "$img_dir" --load
  if [[ "$PUSH" = true ]]; then
    docker push "$image_ref"
  fi
done

# logout
docker logout ghcr.io || true

echo "Done"
