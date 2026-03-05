#!/usr/bin/env bash
set -euo pipefail

# deploy_portainer.sh
# Uploads a docker-compose string to Portainer and creates/updates a stack

usage() {
  cat <<EOF
Usage: $0 --stack-name NAME --compose-file FILE [--endpoint-id ID] [--portainer-url URL] [--token TOKEN]

Options:
  --stack-name NAME      Stack name in Portainer
  --compose-file FILE    Local docker-compose.yml file to upload as a string
  --endpoint-id ID       Portainer endpoint ID (overrides PORTAINER_ENDPOINT_ID)
  --portainer-url URL    Portainer base URL (overrides PORTAINER_URL)
  --token TOKEN          Portainer JWT token (overrides PORTAINER_TOKEN)
EOF
}

STACK_NAME=""
COMPOSE_FILE=""
ENDPOINT_ID="${PORTAINER_ENDPOINT_ID:-}"
PORTAINER_URL="${PORTAINER_URL:-}"
TOKEN="${PORTAINER_TOKEN:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stack-name) STACK_NAME="$2"; shift 2;;
    --compose-file) COMPOSE_FILE="$2"; shift 2;;
    --endpoint-id) ENDPOINT_ID="$2"; shift 2;;
    --portainer-url) PORTAINER_URL="$2"; shift 2;;
    --token) TOKEN="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

if [[ -z "$STACK_NAME" || -z "$COMPOSE_FILE" ]]; then
  echo "--stack-name and --compose-file are required" >&2
  usage
  exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Compose file not found: $COMPOSE_FILE" >&2
  exit 1
fi

if [[ -z "$PORTAINER_URL" || -z "$ENDPOINT_ID" || -z "$TOKEN" ]]; then
  echo "PORTAINER_URL, PORTAINER_ENDPOINT_ID, and PORTAINER_TOKEN must be provided (or via args)" >&2
  exit 1
fi

COMPOSE_CONTENT=$(sed 's/"/\\"/g' "$COMPOSE_FILE")

# Check if stack exists
exists_status=$(curl -sS -H "Authorization: Bearer $TOKEN" "$PORTAINER_URL/api/stacks?endpointId=$ENDPOINT_ID&search=$STACK_NAME")

stack_id=$(echo "$exists_status" | jq -r '.[0].Id // empty')

if [[ -n "$stack_id" ]]; then
  echo "Updating existing stack id=$stack_id"
  # Update via endpoint: method=string
  # Prepare payload and call Portainer API
  payload=$(jq -n --arg compose "$COMPOSE_CONTENT" --arg endpointId "$ENDPOINT_ID" '{StackFileContent: $compose, EndpointID: ($endpointId|tonumber)}')
  resp=$(curl -sS -X PUT -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload" "$PORTAINER_URL/api/stacks/$stack_id?endpointId=$ENDPOINT_ID&method=string")
  if [[ $? -ne 0 ]]; then
    echo "Failed to update stack" >&2
    echo "$resp" >&2
    exit 1
  fi
  echo "Update response: $resp"
else
  echo "Creating new stack $STACK_NAME"
  payload=$(jq -n --arg name "$STACK_NAME" --arg compose "$COMPOSE_CONTENT" --arg endpointId "$ENDPOINT_ID" '{Name: $name, StackFileContent: $compose, EndpointID: ($endpointId|tonumber)}')
  resp=$(curl -sS -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload" "$PORTAINER_URL/api/stacks?endpointId=$ENDPOINT_ID&method=string")
  if [[ $? -ne 0 ]]; then
    echo "Failed to create stack" >&2
    echo "$resp" >&2
    exit 1
  fi
  echo "Create response: $resp"
fi

echo "Done"