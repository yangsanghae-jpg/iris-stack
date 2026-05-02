#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
echo "== docker compose config =="
docker compose config
echo
echo "== env file =="
cat .env
echo
echo "CONFIG CHECK OK"
