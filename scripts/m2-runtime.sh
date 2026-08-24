#!/usr/bin/env bash
set -euo pipefail

STACK_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE_DIR="${M2_WORKSPACE_ROOT:-$(cd "$STACK_DIR/.." && pwd)}"
ENV_FILE="${IRIS_M2_ENV_FILE:-$STACK_DIR/.env.m2}"

if [[ ! -f "$ENV_FILE" ]]; then
  ENV_FILE="$STACK_DIR/.env.m2.example"
fi

compose_m2() {
  docker compose --env-file "$ENV_FILE" -f "$STACK_DIR/compose.m2.yml" "$@"
}

ensure_shared_network() {
  if ! docker network inspect iris-net >/dev/null 2>&1; then
    docker network create iris-net >/dev/null
  fi
}

env_value() {
  local key="$1"
  awk -F= -v wanted="$key" '
    $0 !~ /^[[:space:]]*#/ && $1 == wanted {
      sub(/^[^=]*=/, "")
      print
      exit
    }
  ' "$ENV_FILE"
}

value_or_default() {
  local name="$1"
  local fallback="$2"
  local shell_value="${!name:-}"
  local file_value=""
  if [[ -n "$shell_value" ]]; then
    printf '%s\n' "$shell_value"
    return
  fi
  file_value="$(env_value "$name")"
  printf '%s\n' "${file_value:-$fallback}"
}

normalize_products() {
  local raw="$*"
  if [[ -z "$raw" ]]; then
    raw="$(value_or_default M2_PRODUCTS "")"
  fi
  raw="${raw//,/ }"
  if [[ " $raw " == *" all "* ]]; then
    raw="spc aps sales qms"
  fi
  printf '%s\n' "$raw"
}

product_repo() {
  case "$1" in
    spc) printf '%s\n' "$WORKSPACE_DIR/iris-spc" ;;
    aps) printf '%s\n' "$WORKSPACE_DIR/iris-aps" ;;
    sales) printf '%s\n' "$WORKSPACE_DIR/iris-sales" ;;
    qms) printf '%s\n' "$WORKSPACE_DIR/iris-qms" ;;
    *) return 1 ;;
  esac
}

product_health_url() {
  case "$1" in
    spc) value_or_default M2_SPC_HEALTH_URL "http://127.0.0.1:3340/health" ;;
    aps) value_or_default M2_APS_HEALTH_URL "http://127.0.0.1:7010/api/health" ;;
    sales) value_or_default M2_SALES_HEALTH_URL "http://127.0.0.1:3400/api/v1/health" ;;
    qms) value_or_default M2_QMS_HEALTH_URL "http://127.0.0.1:3350/health" ;;
    *) return 1 ;;
  esac
}

validate_product() {
  local product="$1"
  local repo
  repo="$(product_repo "$product")" || {
    echo "Unsupported product: $product" >&2
    exit 2
  }
  if [[ ! -f "$repo/compose.yml" ]]; then
    echo "Missing product compose file: $repo/compose.yml" >&2
    exit 2
  fi
}

start_products() {
  local products="$1"
  local product repo
  for product in $products; do
    validate_product "$product"
    repo="$(product_repo "$product")"
    docker compose -f "$repo/compose.yml" up -d --wait --wait-timeout 90
  done
}

check_url() {
  local label="$1"
  local url="$2"
  if curl -fsS --max-time 10 "$url" >/dev/null; then
    echo "OK   $label $url"
  else
    echo "FAIL $label $url" >&2
    return 1
  fi
}

preflight_ollama() {
  local host_url model tags
  host_url="$(value_or_default M2_OLLAMA_HOST_URL "http://127.0.0.1:11434")"
  model="$(value_or_default M2_LLM_MODEL "qwen3.5:4b")"
  tags="$(curl -fsS --max-time 10 "$host_url/api/tags")" || {
    echo "Ollama is not reachable at $host_url" >&2
    return 1
  }
  IRIS_M2_EXPECTED_MODEL="$model" python3 -c '
import json
import os
import sys

payload = json.load(sys.stdin)
expected = os.environ["IRIS_M2_EXPECTED_MODEL"]
models = {item.get("name") for item in payload.get("models", [])}
if expected not in models:
    print(f"Required M2 model is not installed: {expected}", file=sys.stderr)
    raise SystemExit(1)
print(f"OK   Ollama model {expected}")
' <<<"$tags"
}

verify_runtime() {
  local products="$1"
  local port product
  port="$(value_or_default L2_GATEWAY_PORT "8011")"
  check_url "l2-ready" "http://127.0.0.1:$port/ready"
  for product in $products; do
    validate_product "$product"
    check_url "$product" "$(product_health_url "$product")"
  done
}

usage() {
  cat <<'EOF'
Usage: scripts/m2-runtime.sh COMMAND [spc aps sales qms|all]

Commands:
  config          Validate and print the effective M2 Compose config
  test            Run policy unit tests and validate Compose
  preflight       Check Ollama and the configured 4B model
  build           Build only the M2 L2 image
  up              Start selected products, then M2 L2
  status          Show containers and check selected health endpoints
  verify-runtime  Require L2 and selected products to be healthy
  down            Stop only the M2 L2 project

With no product arguments, M2_PRODUCTS from .env.m2 is used.
EOF
}

command="${1:-}"
if [[ -z "$command" ]]; then
  usage
  exit 2
fi
shift
products="$(normalize_products "$@")"

case "$command" in
  config)
    compose_m2 config
    ;;
  test)
    PYTHONPATH="$STACK_DIR/l2-gateway" python3 -m unittest discover \
      -s "$STACK_DIR/l2-gateway/tests" -p 'test_*.py'
    compose_m2 config --quiet
    ;;
  preflight)
    preflight_ollama
    ;;
  build)
    compose_m2 build l2-gateway
    ;;
  up)
    preflight_ollama
    ensure_shared_network
    start_products "$products"
    compose_m2 up -d --build --wait --wait-timeout 90 l2-gateway
    verify_runtime "$products"
    ;;
  status)
    compose_m2 ps -a
    verify_runtime "$products"
    ;;
  verify-runtime)
    verify_runtime "$products"
    ;;
  down)
    compose_m2 down
    ;;
  *)
    usage
    exit 2
    ;;
esac
