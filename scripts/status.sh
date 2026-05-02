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
