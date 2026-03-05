#!/bin/bash
# Storage Migration Script
# Moves Docker volumes → /mnt/data_disk/data/
# Run with: sudo bash migrate-storage.sh

set -e
PORTAINER_URL="http://127.0.0.1:9000"
API_KEY="ptr_KIihZqMjydnFofN4j/ypFBa8di1xT9JnXiL4gkQy0R4="

echo "=== Step 1: Create target directories ==="
mkdir -p /mnt/data_disk/data/postgres
mkdir -p /mnt/data_disk/data/haystack
mkdir -p /mnt/data_disk/data/rag-docs/originals
mkdir -p /mnt/data_disk/data/rag-docs/meta
echo "✅ Directories created"

echo ""
echo "=== Step 2: Stop postgres stack (ID 36) ==="
curl -s -X POST "$PORTAINER_URL/api/stacks/36/stop" -H "X-API-Key: $API_KEY"
echo ""
sleep 5

echo "=== Step 3: Stop haystack stack (ID 50) ==="
curl -s -X POST "$PORTAINER_URL/api/stacks/50/stop" -H "X-API-Key: $API_KEY"
echo ""
sleep 5
echo "✅ Stacks stopped"

echo ""
echo "=== Step 4: Migrate postgres data ==="
rsync -av --progress /var/lib/docker/volumes/pgvector_data/_data/ /mnt/data_disk/data/postgres/
chown -R 999:999 /mnt/data_disk/data/postgres/
echo "✅ Postgres data migrated"

echo ""
echo "=== Step 5: Migrate haystack app ==="
rsync -av --progress /var/lib/docker/volumes/haystack_app/_data/ /mnt/data_disk/data/haystack/
echo "✅ Haystack app migrated"

echo ""
echo "=== Step 6: Update postgres stack compose ==="
POSTGRES_COMPOSE=$(cat /home/andrei/.openclaw/workspace/services/postgres-pgvector/docker-compose.yml)
curl -s -X PUT "$PORTAINER_URL/api/stacks/36?endpointId=3" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"stackFileContent\": $(echo "$POSTGRES_COMPOSE" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'), \"pullImage\": false}"
echo ""
echo "✅ Postgres compose updated"

echo ""
echo "=== Step 7: Update haystack stack compose ==="
HAYSTACK_COMPOSE=$(cat /home/andrei/.openclaw/workspace/services/haystack-stack/docker-compose.yml)
curl -s -X PUT "$PORTAINER_URL/api/stacks/50?endpointId=3" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"stackFileContent\": $(echo "$HAYSTACK_COMPOSE" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'), \"pullImage\": false}"
echo ""
echo "✅ Haystack compose updated"

echo ""
echo "=== Step 8: Start postgres stack ==="
curl -s -X POST "$PORTAINER_URL/api/stacks/36/start" -H "X-API-Key: $API_KEY"
echo ""
sleep 10

echo "=== Step 9: Start haystack stack ==="
curl -s -X POST "$PORTAINER_URL/api/stacks/50/start" -H "X-API-Key: $API_KEY"
echo ""
sleep 5

echo ""
echo "=== Step 10: Verify ==="
echo "Waiting 30s for services to start..."
sleep 30
echo -n "Postgres: "
docker exec postgres-pgvector-db-1 pg_isready -U andrei -d vectordb 2>/dev/null && echo "✅ healthy" || echo "❌ not ready"
echo -n "Haystack: "
curl -sf http://127.0.0.1:8000/health && echo "" || echo "❌ not ready"

echo ""
echo "=== Migration complete! ==="
echo "Old Docker volumes (pgvector_data, haystack_app) kept for safety — delete manually when confirmed."
