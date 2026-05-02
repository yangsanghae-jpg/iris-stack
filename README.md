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
