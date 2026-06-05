# IRIS 아키텍처 인덱스

> **기준일:** 2026-06-05 (V2.5 정본 + V2.5.1 부록 반영)
> **정식 사양서:** [docs/system/IRIS_V2.5_계층구조_2026-05-22.md](docs/system/IRIS_V2.5_계층구조_2026-05-22.md) — 본 문서는 그 인덱스/요약본
> **흡수 결정 부록:** [docs/system/IRIS_V2.5.1_external_absorption_2026-06-05.md](docs/system/IRIS_V2.5.1_external_absorption_2026-06-05.md) — 외부 LLM Wiki V1.0 흡수/거부 매트릭스
> **목적:** 폴더는 그대로 두고, 계층 코드(L0–L6)를 [_layers/](_layers/) 심볼릭 링크 + 본 문서로 정리.

## 한 줄 그림

```
사용자
  ⇅
[L1 대화면 / 통제단]   L1-claw  ⇆  L1-webui (양립 정식)
  ⇅
[L2 게이트웨이]   L2-gateway  ── 검색결정 / 라우팅 / context 주입 / trace
  ⇅                ├── LLM:  host Ollama (qwen3:30b 외)
  │                ├── 검색: L4-RS-search (Firecrawl)
  │                └── 메모리: L3-memory  (코드 완료, 현재 토글 OFF)
  ⇅
[L4-K 지식센터]   K1 Intake → K2 Cleansing → K3 Classify → K4 Store → K5 Retrieval → K6 Curate
  ⇅              (단일 엔드포인트 /api/v1/retrieval + X-IRIS-Caller 헤더 / Telemetry Zero)
[L5 감시단]       Telemetry / Fallback 10% 알람 → L1 통보
  ⇅
[L6 검증단]   L6-D1 diagnosis (첫 소비자) — *목적이 아니라 K5 계약을 두드려 보는 Sandbox*
```

> **무게중심은 L4-K 지식센터.** L4-C(코드 게이트웨이)와 cursor는 보조 갈래.
> **V2.5 핵심 결정:** L6는 마일스톤의 *목적*이 아니라 *K5 계약의 결함을 드러내는 검증단*. Fallback 10% 초과 시 L1(주인)에게 즉시 고발.

## 계층 매핑

| 코드 | 실제 폴더 | 역할 | 상태 |
|---|---|---|---|
| **L0-stack** | [iris-stack/](iris-stack/) | 런타임/오케스트레이션 (docker-compose, iris-net) | ✅ 운영 |
| **L1-webui** | (L0-stack 내부 OpenWebUI 컨테이너, 포트 3000) | 사용자 대화면 (정식 ①) | ✅ 운영 |
| **L1-claw** | [iris-claw/](iris-claw/) | 사용자 대화면 (정식 ②, OpenClaw) | 🟡 워크스페이스만 존재, stack 와이어링 미구현 |
| **L1-ollamaui** | [L1-web-chat/](L1-web-chat/) | Ollama 직결 미니 UI | 🔵 실험 (L2 우회) |
| **L2-gateway** | [iris-stack/l2-gateway/](iris-stack/l2-gateway/) | OpenAI 호환 라우터, 포트 8010 | ✅ 운영 (검색결정·trace·stream·메모리 와이어링까지 완료) |
| **L3-memory** | [iris-memory/](iris-memory/) | 워킹 메모리 (FastAPI+SQLite, 포트 8001) | ✅ 단독 동작, L2 통합은 토글 OFF |
| **L4-RS-search** | [iris-stack/l4-search/](iris-stack/l4-search/) | 웹 검색 전문가 (Firecrawl SDK v1.18, 포트 8020) | ✅ 운영 |
| **L4-RS-spike** | [L4-search/](L4-search/) | Firecrawl SDK v4 업그레이드 스파이크 | 🔵 실험 |
| **L4-K-knowledge** | [iris-system/](iris-system/) | **지식센터** (K1~K6 sub-layer, V2.5 정본) — raw / wiki / engine / retrieval / lint / sqlite + FTS5 + FAISS(예정) | 🟡 골격 가동, **router/wiki 미기동 (Phase 0.5에서 Docker 기동 예정)** |
| **L4-C-gateway** | [iris-gateway/](iris-gateway/) | 코드/태스크 게이트웨이 (`/task/ask|code|workflow`) | 🟡 analysis-only, L3 라이브 연동 |
| **L5-observability** | [iris-stack/observability/](iris-stack/observability/) — Prometheus + Grafana + Loki + Promtail + cAdvisor + node/blackbox exporters | Telemetry Zero — caller별 fallback 10% 알람 → L1 통보 | ✅ **인프라 운영 중 (M5 13h Up), K5 패널 `iris-v25-k5.json` 대기** |
| **L6-diagnosis** | [diagnosis-tool/](diagnosis-tool/) | 첫 도메인 산출물 — **K5 계약 검증단** (V1.5) | ✅ api + llm-gateway + md2img 운영 중, **K5 호출 전환은 Phase 5.7** |

심볼릭 링크는 [_layers/](_layers/) 디렉터리에서 코드명으로 직접 접근 가능.

## LLM/검색 백엔드 요약

- **LLM 단일 허브:** 호스트 Ollama (`host.docker.internal:11434`)
  - L1-ollamaui → 직결, L2-gateway → `/api/chat`, L4-C-gateway → `/v1/chat/completions`
  - 외부 API(OpenAI/Anthropic) 미사용
- **검색:**
  - L4-RS-search / L4-RS-spike → Firecrawl
  - L1-claw 자체 도구 → Tavily (별도 경로)

## L4-K(지식센터) 현 골격 — iris-system 내부 (V2.5 K1~K6 매핑)

| 구성 | 파일 | V2.5 sub-layer |
|---|---|---|
| Source Intake (사용자 Drop / 외부 정본 No-Copy) | [iris-system/knowledge/raw/](iris-system/knowledge/raw), [iris-system/apps/ingest/](iris-system/apps/ingest/) | **K1** (K1a~c Bronze + K1d Reference) |
| Cleansing | (K1d는 우회, K1a~c는 V2.6 E2E) | **K2** |
| Classify (matrix key `industry / area / level`) | [iris-system/apps/ingest/schema.sql](iris-system/apps/ingest/schema.sql) | **K3** |
| Store (SQLite + FTS5 + FAISS 예정) | [iris-system/knowledge/_index.db](iris-system/knowledge/), [iris-system/apps/wiki/engine.py](iris-system/apps/wiki/engine.py) | **K4** |
| Retrieval (단일 엔드포인트 `/api/v1/retrieval` + `X-IRIS-Caller`) | [iris-system/apps/wiki/retrieval.py](iris-system/apps/wiki/retrieval.py), [iris-system/apps/router/server.py](iris-system/apps/router/server.py) | **K5** (사양: V2.5, 현재 구현: `/wiki/*`) |
| Curate (Trigger A/B/C, Gold 후보 식별) | [iris-system/apps/wiki/lint.py](iris-system/apps/wiki/lint.py), [iris-system/apps/wiki/history.py](iris-system/apps/wiki/history.py) | **K6** |
| 정책·룰 | [iris-system/knowledge/CLAUDE.md](iris-system/knowledge/CLAUDE.md), [IRIS_WIKI_QUALITY_RULES.md](iris-system/knowledge/IRIS_WIKI_QUALITY_RULES.md) | (전 단계) |
| Quartz 발행 (보조) | [iris-system/apps/quartz/](iris-system/apps/quartz/) | K6 보조 도구, V2.6 본격 발행 |

## 우선순위 (V2.5 정본 §11 + V2.5.1 흡수 §4 통합, 2026-06-05)

V2.5 마일스톤 완료 기준 (사양 §10): 정상호출 비율 ≥ 95%, Gold 후보 ≥ 3, `X-IRIS-Caller` 누락률 < 1%, 가용성 ≥ 99%.

진행 중 (V2.5 잔여):

1. 🔴 **K5 단일 엔드포인트 `/api/v1/retrieval`** — 사양 확정, 현재 구현은 `/wiki/*`까지
2. 🔴 **L6-D1 K5 호출 전환** — Embedded Fallback + Telemetry caller별 10% 알람
3. 🔴 **시맨틱 검색 활성화** — Ollama 임베딩 + FAISS 외부 인덱스 (sqlite-vec 우회)

V2.6 로드맵 (V2.5 §11 + V2.5.1 §4 + §7 Phase 0.5):

4. 🔴 **Phase 0.5 — iris-system Docker 기동 + storage 분리** (M5 진단 결과, 모든 후속 Phase의 게이트)
5. 🔴 **K3 `kind` / `origin` 컬럼 + K6 입력 필터** — Echo Chamber 차단 (V2.5.1 §2.A·§2.D)
6. 🔴 **`lane='secure'` 차단 게이트** — K1~K6 보안 (V2.5.1 §2.A)
7. 🔴 **K1a 비정형 E2E 가동** — PDF/PPT Drop → silver 자동 승격 (Trigger B 실효화)
8. 🟡 **Gold Lane 공식 승격 + 양식 확정**
9. 🟡 **Golden Q&A 50문항 + 평가 하네스** (V2.5.1 §2.D)
10. 🟡 **L1-claw ↔ L2-gateway 통합** (V2.5.1 §2.A "MCP-only 강화"와 연결)
11. ✅ ~~L5 Observability 대시보드화~~ — **이미 구현됨** (Grafana + Loki + Promtail 7컨테이너 운영 중, K5 기동 후 자동 점등)
12. 🟡 **Quartz v4 발행 채널 개방** (K6 보조)
13. 🟢 **K5 Skill thin wrapper 시범 1~2개** (V2.5.1 §2.C, L6 충분성 확인 후)
14. 🟢 **L3-memory 토글 ON**

## 관련 문서

- **정본 사양 (V2.5):** [docs/system/IRIS_V2.5_계층구조_2026-05-22.md](docs/system/IRIS_V2.5_계층구조_2026-05-22.md)
- **흡수 부록 (V2.5.1):** [docs/system/IRIS_V2.5.1_external_absorption_2026-06-05.md](docs/system/IRIS_V2.5.1_external_absorption_2026-06-05.md)
- **L4-K 설계서:** [iris-system/docs/system_design_ko.md](iris-system/docs/system_design_ko.md)
- **이력:** [docs/system/](docs/system/) (V2.0 / V2.1 / V2.3 / V2.4 보존)
- **외부 레퍼런스:** [docs/system/reference/external_v1/](docs/system/reference/external_v1/) — LLM Wiki V1.0 (참조용, 사양 아님)
- **메모리:** `~/.claude/projects/-Users-iris-Documents-0Dev/memory/MEMORY.md`
