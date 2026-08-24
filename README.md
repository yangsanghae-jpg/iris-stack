# IRIS Local Stack

## Purpose

This folder manages the local Docker-based IRIS service stack.

Current target:

1. Docker baseline
2. OpenWebUI
3. L2 Gateway -> Ollama

## Current Scope

Step 1 only creates the Docker baseline.

No containers should be started in Step 1.

## Host Services

Ollama runs on the Mac host:

```text
http://127.0.0.1:11434
```

Docker containers will access host Ollama through:

```text
http://host.docker.internal:11434
```

## Planned Ports

| Service | Host Port | Note |
|---------|-----------|------|
| OpenWebUI | 3000 | Step 2 |
| L2 Gateway | 8010 | Step 3 |
| Ollama | 11434 | Host Mac, not Docker |

## Do Not Include Yet

* OpenClaw
* Firecrawl / L4-search
* iris-memory
* diagnosis-tool
* LM Studio

> **Note (v0.1 baseline):** The stack now includes **L4-search** and Firecrawl-backed search. The bullets above are historical “out of scope” notes from earlier steps and are kept for traceability; the section **IRIS Stack v0.1 — L2/L4 Search Baseline** below describes the current architecture.

---

## IRIS Stack v0.1 — L2/L4 Search Baseline

### Current Architecture

```text
OpenWebUI
→ L2 Gateway
→ Ollama local models
→ L4-search
→ Firecrawl
```

### Services

| Service | Container | Port | Role |
|---------|-----------|-----:|------|
| OpenWebUI | iris-open-webui | 3000 | L1 chat UI |
| L2 Gateway | iris-l2-gateway | 8010 | OpenAI-compatible routing gateway |
| L4 Search | iris-l4-search | 8020 | Firecrawl search wrapper |
| Ollama | host process | 11434 | Local LLM runtime |

### Main Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/health` | GET | L2 status |
| `/v1/models` | GET | OpenAI-compatible model list |
| `/v1/chat/completions` | POST | OpenAI-compatible chat endpoint |
| `/search/health` | GET | L2 → L4 health proxy |
| `/search` | POST | L2 → L4 search proxy |
| `/debug/search-decision` | POST | Search trigger debug |

### Verified Capabilities

- OpenWebUI can call L2 Gateway through OpenAI-compatible API.
- L2 Gateway can call Ollama local models.
- L2 Gateway can decide when search is needed.
- L2 Gateway can call L4-search.
- L4-search can call Firecrawl.
- Search results can be injected into the model context.
- Search answers include `[IRIS 검색 출처]`.
- `stream=true` is supported for OpenWebUI compatibility.

### Known Limitations

- Search quality is still basic.
- Query rewriting is not yet robust.
- Source ranking is weak.
- Financial, stock, legal, and high-confidence factual domains need domain-specific adapters.
- Qwen thinking leakage may still require additional sanitizing.
- L3 memory is not connected yet.

### Baseline Verification

From the repository root:

```bash
cd /Users/iris/0Dev/iris-stack
docker compose ps
curl -sS http://127.0.0.1:8010/health | python3 -m json.tool
curl -sS http://127.0.0.1:8020/health | python3 -m json.tool
curl -sS http://127.0.0.1:8010/v1/models | python3 -m json.tool | head -80
```

Optional: `./scripts/status.sh` (from `iris-stack`) prints compose status, L2/L4 health, and a sample of `/v1/models`.

## M2 Lightweight Runtime

M2 uses a separate Compose file that starts only L2. OpenWebUI, OpenClaw, web search, memory, and the observability stack are excluded from this profile.

```bash
cp .env.m2.example .env.m2
./scripts/m2-runtime.sh test
./scripts/m2-runtime.sh preflight
./scripts/m2-runtime.sh up spc qms
```

The default policy allows only `qwen3.5:4b`, caps context at 8K tokens and output at 1,024 tokens, and publishes L2 on `127.0.0.1:8011`. See [docs/M2_RUNTIME_PHASE1.md](docs/M2_RUNTIME_PHASE1.md).

### Git Baseline Tag

This baseline is intended to be tagged as:

`v0.1-l2-l4-search-baseline`

Do not put `.env` contents, Firecrawl API keys, or tokens in the README. Repository URLs, if mentioned, should be name-only without secrets.
