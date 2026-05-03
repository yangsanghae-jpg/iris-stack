#!/usr/bin/env bash
set -euo pipefail
echo "== IRIS Stack Path =="
pwd
echo
echo "== Docker Compose Config =="
docker compose config >/tmp/iris-stack-compose-check.yml
echo "compose config: OK"
echo
echo "== Docker Containers =="
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo
echo "== IRIS Stack Services =="
docker compose ps
echo ""
echo "== L2 Health =="
curl -sS "http://127.0.0.1:${L2_GATEWAY_PORT:-8010}/health" || true
echo ""
echo "== L4 Health =="
curl -sS "http://127.0.0.1:${L4_SEARCH_PORT:-8020}/health" || true
echo ""
echo "== L2 Models sample =="
curl -sS "http://127.0.0.1:${L2_GATEWAY_PORT:-8010}/v1/models" | head -500 || true
echo
echo "== Docker System DF =="
docker system df
echo
echo "== Port Check =="
for p in 3000 8010 11434 18020; do
  echo "--- port :$p"
  lsof -i :$p || true
done
echo
echo "== Ollama Host Check =="
curl -s http://127.0.0.1:11434/api/tags | python3 -m json.tool | head -80 || true
