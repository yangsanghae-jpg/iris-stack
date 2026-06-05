# IRIS V2.3 계층 구조 — 2026-05-15 기준

> **버전:** 2.3 (rev 4 — **계층 재정립**: L4-C 코딩→L7 분리, L4-K 내부 K1~K6 sub-layer 명시, L6 4종 분류로 L4-K 연계성 강조)
> **이전 버전:** V2.2 rev 3 (같은 날 오후), V2.1 rev 2 (같은 날 오전), V2.0 (2026-05-03)
> **상태:** L1 양립 + L2 Gateway + L4-S Search + L3 Memory 라이브 ON. L4-K 지식센터 v0 골격 + V2.3에서 6 sub-layer(K1~K6) 골격 확정. 구현 미시작.
> **무게중심:** **L4-K 지식센터(iris-지식).** L7 (코딩·런타임·검증·스파이크) 등 보조 갈래는 L4에서 분리.

---

## V2.0 → V2.1 → V2.2 → V2.3 핵심 변경

| # | 항목 | V2.0 (5/3) | V2.1 (5/15 오전) | V2.2 (5/15 오후) | V2.3 (5/15 저녁) |
|---|---|---|---|---|---|
| 1 | **저장소 경로** | `/Users/iris/0Dev/iris-stack` | `/Users/iris/Documents/0Dev/` | — | — |
| 2 | **L1 정책** | OpenWebUI 단일 | webui + claw 양립 | — | — |
| 3 | **L3 Memory** | "다음 단계" | L2 코드 완료, OFF | **라이브 ON** | — |
| 4 | **L4-K 지식센터** | "미구현" | v0 골격 식별 | 3계층/3-Lane/저장 스택 확정 | **K1~K6 sub-layer 명시 (Intake/Cleansing/Classify/Store/Search/Curate)** |
| 5 | **L4-K 저장 구분** | 미정 | 미정 | Bronze→Silver→Gold | — |
| 6 | **L4-K 인테이크** | 미정 | 미정 | 3-Lane (A/B/C) | — |
| 7 | **L4-K 저장 기술** | 미정 | sqlite | SQLite+FTS5+sqlite-vec+Ollama embed | — |
| 8 | **L4-K 저작** | 미정 | 미정 | Obsidian vault | — |
| 9 | **L4-S Search** | (L4-RS) Firecrawl v1.18 | + spike | Quick Clip 재사용 | **L4-RS → L4-S로 코드명 변경** |
| 10 | **L4-C 코딩** | Cursor 외부 | iris-gateway 신규 | — | **L4에서 분리 → L7-C로 이주** (성격 상이) |
| 11 | **L4-R 런타임** | L4 내부 | — | — | **L7-R로 이주** |
| 12 | **L4-V 검증** | L4 내부 | — | — | **L7-V로 이주** |
| 13 | **L4-RS-spike** | — | L4 내부 | — | **L7-S로 이주 (스파이크/실험)** |
| 14 | **L6 Application** | "후보" 나열 | L6-diagnosis 정식 | 매트릭스 키 확정 | **L6-D/R/C/X로 4분류 (L4-K 연계성 명시)** |
| 15 | **L7 Developer Tooling** | 없음 | 없음 | 없음 | **신설** (L4에서 분리된 보조 계층) |
| 16 | **계층 코드** | 문서상 | `_layers/` 심볼릭 + ARCHITECTURE.md | — | **L4-C/R/V → L7-C/R/V/S 이름 변경 반영** |

---

## 한 줄 그림 (V2.3)

```
              [L0 User]
                  │
        [L1 Interaction]  ─── webui · claw · ollamaui
                  │
        [L2 Gateway]  ─── 해석·라우팅·context
                  │
       ┌──────────┼───────────┐
       ▼          ▼           ▼
 [L3 Memory]  [L4-S]   [L4-K Knowledge ★]
   working    Search    K1 Intake → K2 Cleansing → K3 Classify
   memory   (Firecrawl)         → K4 Store → K5 Search ← K6 Curate
                                      │
                                      │ Retrieval API (매트릭스/FTS/벡터)
                                      ▼
                              [L6 Application]
                              D 도메인 · R 보고서 · C 대화 · X 미래
                                      │
                                  ┌───┴───┐
                                  ▼       ▼
                              L6-D     L6-C  (대화도 L4-K 응답으로 회귀)
                              diagnosis  L1+L2가 L4-K 조회
   ─────────────────────────────────────────────────────
   [L5 Sensor / Trace / Governance]  ── 모든 계층 횡단
   [L7 Developer Tooling] ── C 코딩 · R 런타임 · V 검증 · S 스파이크
                            (L4-K 자산 운영·보조, 사용자 경로 외부)
```

---

## [L0] User Layer

- **[L0-U1] User**
  - 역할: 목표 정의 / 지시 / 승인 / 피드백 / 결과 점검
  - 진입 채널 (V2.1 양립):
      1. L1-webui (OpenWebUI)
      2. **L1-claw (OpenClaw)** — V2.0의 "보류" → V2.1 정식 후보
      3. (실험) L1-ollamaui — Ollama 직결
      4. (향후) WeChat / Feishu / 기타
  - LLM: 없음

→

## [L1] Interaction / Supervisor Entry Layer

- **[L1-S1] User Entry Interface — L1-webui**
  - 구현: OpenWebUI 컨테이너 (`iris-open-webui`, 포트 3000)
  - 위치: [iris-stack/docker-compose.yml](iris-stack/docker-compose.yml)
  - 상태: ✅ 운영
- **[L1-S1'] User Entry Interface — L1-claw** *(V2.1 신규 정식)*
  - 구현: OpenClaw (`openclaw@^2026.5.6`)
  - 위치: [iris-claw/](iris-claw/) (워크스페이스 + `node_modules/openclaw`)
  - 워크스페이스: [openclaw-workspace/](iris-claw/openclaw-workspace) (IDENTITY/SOUL/MEMORY/SKILLS/TOOLS)
  - 자체 검색 도구: Tavily ([tools/search/search_web.py](iris-claw/tools/search/search_web.py))
  - **현재 동작 특이점:** L1 표면이지만 **자체적으로 LLM 직접 호출 + 자체 검색 라우팅을 수행** → 사실상 *L1 + 자체 L2* 통합 형태로 동작 중. L2-gateway(8010) 미경유.
  - 상태: 🟡 워크스페이스 동작, **L0-stack 와이어링 미구현** (V2.1 우선순위 #3 = 자체 L2 기능을 떼고 L2-gateway로 통합)
- **[L1-S1''] User Entry Interface — L1-ollamaui** *(V2.1 실험)*
  - 구현: 오픈소스 ollama-ui vendoring
  - 위치: [L1-web-chat/ollama-ui/](L1-web-chat/ollama-ui)
  - 특징: **Ollama 직결 (L2 우회)**, Chrome extension 패키징 가능
  - 상태: 🔵 실험 (정식 경로 아님)
- **[L1-S2] Session Entry**
  - 역할: 사용자 요청을 L2-gateway로 전달
  - 현재 webui 경로: OpenWebUI → OpenAI 호환 API → L2-gateway:8010 ✅
  - **현재 claw 경로: 자체 L2-equivalent 라우팅 (LLM·검색 직접 호출)** — L2-gateway 미경유
  - 향후: claw도 L2-gateway 경유로 통일 (V2.1 우선순위 #3)
- **[L1-S3] Conversation Surface**
  - 현재 표시: 답변 + `[IRIS 검색 출처]` 푸터, `iris_trace` 메타
  - 미구현: 다중 태스크 조율, 결과 review 루프
- **[L1-S5] Future External Chat Channels**
  - WeChat / Feishu / DingTalk / Slack — 미구현

LLM: 기본 없음 (L1-ollamaui만 직결)

→

## [L2] Interpretation / Routing / Contract Layer

위치: [iris-stack/l2-gateway/](iris-stack/l2-gateway), 진입 [app/main.py](iris-stack/l2-gateway/app/main.py)

- **[L2-I1] L2 Gateway** — FastAPI `iris-l2-gateway`, 포트 8010
- **[L2-I2] OpenAI-compatible Adapter**
  - `GET /v1/models`, `POST /v1/chat/completions`
- **[L2-I3] Ollama Adapter**
  - `host.docker.internal:11434` → `/api/chat`
  - 모델: qwen3:30b / qwen3.5:4b / qwen3-coder:30b / llama3.2:3b 등
- **[L2-I4] Search Decision Engine**
  - 키워드 기반: `should_use_search()`, `find_matched_triggers()`
  - 트리거 예: 검색 / 찾아봐 / 최신 / 현재 / 뉴스 / 공휴일 / 주가 / 가격 / 일정 / 트렌드
- **[L2-I5] L4-search Router**
  - `http://l4-search:8020/search` → `call_l4_search()`
- **[L2-I6] Context Injection Builder**
  - `build_search_context()` — `[IRIS_SEARCH_CONTEXT] … [/IRIS_SEARCH_CONTEXT]`
  - **(V2.1 신규)** 메모리 컨텍스트도 동일 패턴: `build_memory_context()` → `[IRIS_MEMORY_CONTEXT]`
  - **(V2.1 신규)** 메모리 프로필 번들: `_load_memory_profile_bundle()` → `[IRIS_MEMORY_PROFILE]` (memory-profiles RO mount)
- **[L2-I7] Response Composer**
  - `sanitize_final_answer()` + `build_iris_source_footer()` → 본문 뒤 `[IRIS 검색 출처]`
- **[L2-I8] Stream / Non-stream Compatibility**
  - `_chunk_text_for_sse()` — OpenAI 호환 SSE
- **[L2-I9] Trace Builder**
  - `build_iris_trace()` — search_used / search_ok / search_count / search_urls / route / model / stream / **memory_enabled** (V2.1 추가)
- **[L2-I10] Memory Bridge** *(V2.1 정식 등재)*
  - `call_memory_prefetch()` / `call_memory_writeback()` — L3-memory HTTP 호출
  - env: `IRIS_MEMORY_ENABLED`, `IRIS_MEMORY_BASE_URL`, `IRIS_MEMORY_USER_ID`, `IRIS_MEMORY_PROJECT_ID`
  - **현 컴포즈: `IRIS_MEMORY_ENABLED: "false"` (테스트용 OFF)** — 코드는 라이브 준비 완료

역할: 지시 해석 / 검색 판단 / 모델 라우팅 / context 구성 / **메모리 prefetch·writeback** / trace 생성
LLM: 필수 연결 (Ollama)
구현 상태: **운영 (L3 통합까지 코드 완료)**

→ uses context

## [L3] Working Memory / Context Support Layer

위치: [iris-memory/](iris-memory/), 진입 [app/main.py](iris-memory/app/main.py), 포트 8001 (자체 compose)

> **주의:** L3는 "워킹 메모리"이고 **L4-K(지식센터)와 다른 컴포넌트**다. 헷갈리지 말 것.

- **[L3-M0] iris-memory 서비스** — FastAPI + SQLAlchemy + SQLite (`data/memory.db`), Pydantic v2
- **[L3-M1] User Profile Store** — 라우터 [profile.py](iris-memory/app/routers/profile.py)
- **[L3-M2] Project Memory Store** — 라우터 [memory.py](iris-memory/app/routers/memory.py)
- **[L3-M3] Task History Store** — 라우터 [tasks.py](iris-memory/app/routers/tasks.py)
- **[L3-M4] Skill Memory Store** — 라우터 [skills.py](iris-memory/app/routers/skills.py)
- **[L3-M5] Prefetch / Writeback Contract**
  - `POST /memory/prefetch`, `POST /memory/writeback`
  - 소비자: L2-gateway (코드 완료, 토글 OFF), **L4-C-gateway (라이브)**
- **[L3-A1] memory-admin** — RO viewer ([iris-stack/memory-admin/](iris-stack/memory-admin/), 포트 18020)
  - SQLite를 host bind mount로 직접 조회
- **[L3-P1] memory-profiles** — L2가 system context로 주입할 프로필 파일
  - [iris-stack/memory-profiles/](iris-stack/memory-profiles/) → l2-gateway에 RO mount

역할: 작업 기억 / 최근 결정 / 실행 trace / 재사용 패턴 지원
LLM: 없음
**상태: ✅ 단독 동작 / L2 통합 라이브 ON (V2.2, memory_enabled:true / memory_used:true / memory_writeback_ok:true 확인) / L4-C도 라이브 사용**

→

## [L4] Information Services Layer *(V2.3 재정립)*

> **V2.3 변경:** L4는 **정보 서비스 계층**으로 좁힘. **L4-S (Search Service · 옛 L4-RS)**와 **L4-K (Knowledge Center)** 두 갈래만 유지.
> 코딩(L4-C)·런타임(L4-R)·검증(L4-V)·스파이크(L4-RS-spike)는 **성격이 다르므로 L7 Developer Tooling으로 이주**.
> L4-D(Document)·L4-M(System Memory)은 미구현 상태로 L4-X(미래) 안에 정리.

### [L4-S] Search Service *(V2.3 코드명, 옛 L4-RS)*

- **[L4-S1] l4-search Service** — [iris-stack/l4-search/](iris-stack/l4-search/), 포트 8020
  - Express ([server.js](iris-stack/l4-search/server.js))
  - Firecrawl SDK v1.18
- **[L4-S2] Firecrawl Adapter** — `/search` (title / url / snippet 반환)
- **[L4-S3] Search Result Normalizer** — IRIS 표준 JSON 정리, L2가 `score_search_result_relevance` / `filter_search_results`로 후처리
- **[L4-S4] Future Source Fetcher** — scrape / markdown 추출 (미구현)

**소비자 2종 (V2.3 명시):**
1. **L2 Gateway** — 채팅 검색 트리거 시 단발 호출
2. **L4-K1b Quick Clip** — Bronze 인테이크 차선이 재사용 (외부 URL 1개 fetch)

상태: ✅ L2 연결 완료 / LLM 없음 / Firecrawl API

### [L4-K] Knowledge Center ★ 무게중심

위치: **[iris-system/](iris-system/)** — V2.3에서 **6개 sub-layer(K1~K6)**로 내부 골격 확정.

**Lifecycle**

```
K1 Intake → K2 Cleansing → K3 Classify → K4 Store ↔ K5 Search ← K6 Curate
(3-Lane Bronze) (자동 파이프라인)  (auto+사람)  (Bronze/Silver/Gold)        (사람 + LLM 보조)
                                                       │
                                                       ▼
                                                  L6 Application 공급
```

**저장 3계층 (V2.2 확정, V2.3 유지)**

```
[① Bronze 1차 RAW]  →  [② Silver 2차 클렌징]  →  [③ Gold 3차 최종]
knowledge/raw/         knowledge/staging/         knowledge/wiki/
(불변, 손실 0)         (자동 파이프라인)          (Obsidian vault, 사람 검수)
        ─── 단방향 (역방향 수정 금지) ───
        ─── 모든 Silver/Gold 행은 source_doc_id로 Bronze 추적 ───
        ─── 통합 인덱스: knowledge/_index.db (lane 컬럼으로 합류) ───
```

#### [K1] Intake — 수집 (3-Lane → Bronze)

| 차선 | 위치 | 트리거 | 신뢰도 | 구현 기술 |
|---|---|---|---|---|
| **K1a Document Drop** | `raw/files/` | 사용자 폴더 투입 | ★★★ verified | watchdog + unstructured / pymupdf4llm / openpyxl |
| **K1b Quick Clip** | `raw/clips/` | 사용자 URL 1개 | ★★ clipped | **L4-S (Firecrawl) 재사용** + trafilatura |
| **K1c Watch List** | `raw/inbox/{YYYY-Www}/` | cron (주 1회) | ★ auto (격리) | RSS / 도메인 화이트리스트, 산업당 캡, 30일 미검토 archive |

**원칙:** 원본 불변. 메타는 `.meta.yaml` 옆 파일에 (SHA256, source_url, fetched_at, fetcher_version, lane, trust).
**시작 순서:** K1a → K1b → K1c.

#### [K2] Cleansing — 정제 (Bronze → Silver 자동)

- **텍스트 추출**: unstructured (범용) / pymupdf4llm (PDF→MD) / MinerU (표 많은 PDF) / openpyxl+pandas (Excel)
- **HTML 정제**: trafilatura
- **언어 감지**: lingua-py
- **중복 제거**: datasketch (MinHash near-duplicate)
- **청킹**: semantic-text-splitter / MarkdownHeaderTextSplitter — 헤더 우선, 표/코드 별도 청크, frontmatter 미포함
- **임베딩**: Ollama `nomic-embed-text` (768d) / 대안 `bge-m3`
- **PII 제거 (선택)**: presidio
- **incremental**: mtime + content hash, 바뀐 문서만 재임베딩
- **산출**: `staging/{doc_id}.md` + SQLite (documents / documents_fts / chunks / chunk_vec)

#### [K3] Classify — 분류 *(V2.3 신규 명시)*

기존엔 K2와 K6 사이에 묻혀있던 단계를 sub-layer로 가시화.

| 종류 | 시점 | 부여 주체 | 라벨 |
|---|---|---|---|
| **K3-A Auto Tagging** | K2 직후 (Silver 적재 시) | 자동 | language / trust tier (verified·clipped·auto) / topic hint (LLM 분류) |
| **K3-H Matrix Coordinate** | K6 Curate 중 | **사람** | `industry (A~H) / area (계획·품질·설비·물류) / level (L0~L4)` |

K3는 단일 컴포넌트가 아니라 **태깅 정책 + 매트릭스 좌표계 정의**가 본질. K5 매트릭스 조회의 키 공급원.

#### [K4] Store — 저장 (3-Tier + 단일 인덱스)

- **3계층 폴더**: `raw/`(Bronze) · `staging/`(Silver) · `wiki/`(Gold)
- **단일 인덱스**: `knowledge/_index.db`
  - `documents` — 메타 (path, lane, trust, industry, area, level, source_url, title, fetched_at, promoted_to)
  - `documents_fts` — FTS5 전문 검색
  - `chunks` — 청크 텍스트
  - `chunk_vec` — sqlite-vec 가상 테이블, FLOAT[768]
- Bronze/Silver/Gold 모두 같은 테이블에 `lane` 컬럼으로 합류. wiki 셀은 `lane='wiki'`로 들어가되 `chunk_vec`엔 미포함 (FTS만)
- 백업: `.db` 파일 + `raw/` (Bronze만 있으면 Silver·Gold 재생성 가능)

**Promotion Gates**

| 전이 | 조건 | 주체 |
|---|---|---|
| Bronze → Silver | 파싱 OK + 길이 임계 + 언어 OK + 중복 아님 | 자동 |
| Silver → Gold | 사람 검수 + frontmatter 필수필드 + 출처 명시 + lint 통과 | **사람 (자동 금지)** |

#### [K5] Search — 검색 (Retrieval API)

| 패턴 | 용도 | 기술 | 소비자 |
|---|---|---|---|
| **① 매트릭스 조회** (결정적) | `WHERE lane='wiki' AND industry=B AND area=품질 AND level=L3` | SQL exact | **L6-D diagnosis** (1차) |
| **② 키워드 검색** | 탐색·lint·중복 검출 | FTS5 MATCH | L6-R reports, 사람 (Obsidian) |
| **③ 의미 검색** | Silver(raw/clips/inbox) 본문에서 유사 출처 | sqlite-vec L2 distance | **K6 Curate 보조** |

- 구현: [apps/wiki/retrieval.py](iris-system/apps/wiki/retrieval.py) — REST 노출
- **V2.3 소비자 확장**: L2 Gateway도 K5를 호출하여 채팅 응답에 지식 컨텍스트 주입 (`[IRIS_KNOWLEDGE_CONTEXT]`) — 검토 단계
- 라우터 [apps/router/server.py](iris-system/apps/router/server.py)

#### [K6] Curate — 큐레이션 (Silver → Gold 저작)

- **저작 도구**: **Obsidian** (vault = `knowledge/wiki/`). Dataview·[[wikilink]]·그래프뷰. 동기화 미사용, git이 정본.
- **매트릭스**: **8산업(A~H) × 4영역(계획·품질·설비·물류) × 5단계(L0~L4)** — diagnosis-tool step4 Baseline 동축
- **frontmatter 필수**: `industry, area, level, status, trust, sources[]`
- **본문 구조**: **미확정** (첫 3~5개 셀로 패턴 발견 후 템플릿화)
- **품질 lint**: [IRIS_WIKI_QUALITY_RULES.md](iris-system/knowledge/IRIS_WIKI_QUALITY_RULES.md) + [apps/wiki/lint.py](iris-system/apps/wiki/lint.py)
- **버전관리**: git diff·리뷰
- **큐레이션 보조**: K5-③ 의미검색으로 관련 Silver 청크 → 사람이 Gold 셀로 정제

#### [L4-K-PL] Pipeline Orchestration

- **Makefile + cron + watchdog** (가벼움 우선)
- 명령: `make ingest-files | clip URL=… | watchlist-run | clean-stage | promote PATH=… | lint-wiki | reindex`
- 중기 (월 1만 문서+): Prefect / Dagster

#### [L4-K-EMB] Embedding & Vector Backend

- 임베딩: Ollama `nomic-embed-text` (로컬 768d) / 대안 `bge-m3`
- 벡터 DB: **sqlite-vec 시작** → 100k 청크 신호 시 **Qdrant single** (VectorStore 인터페이스 추상화로 30분 이주)
- Milvus는 본 프로젝트 수명 내 불필요
- 예상 규모: 8산업 × ~100문서 × ~50청크 ≈ **4만 청크** (sqlite-vec 한도의 1%)

---

역할: 도메인 지식 자산을 6단계 lifecycle (K1~K6)로 영속화, **L6 Application 4종(D·R·C·X)에 공급**
LLM: 큐레이션 보조 + 로컬 임베딩 (실행 결정은 사람)
**상태: 🟡 v0 골격 + V2.3에서 K1~K6 sub-layer + 4 소비자 명시. 구현은 K1a Document Drop부터.**

### [L4-X] Future Information Services

미구현·미래 갈래만 정리 (V2.0의 L4-D Document, L4-M System Memory 포함).

- **L4-X-D · Document System** — L2에서 routing 가능한 문서 서비스 (미구현)
- **L4-X-M · System Memory** — trace 누적·요약·검색 (별도 신설 예정, 미구현). iris-memory(L3)와 구분
- **L4-X-기타** — Diagram / Advanced Research / Data Analysis / Presentation / Translation / External API / Finance / WeChat·Feishu Connector

→

## [L5] Sensor / Trace / Governance Layer

V2.0 골격 유지 + V2.1 보강:

- **[L5-G1] Log Signals** — docker logs / L2 request logs / L4 search logs / **L4-C `logs/task_runs.jsonl`, `errors.jsonl`, `memory_events.jsonl`** (V2.1 추가)
- **[L5-G2] Screenshots / Snapshots** — UI 검증
- **[L5-G3] Runtime Signals** — docker ps / port / health
- **[L5-G4] Verification Status** — PASS / HOLD / FAIL
- **[L5-G5] Trace Records**
  - L2 응답: `iris_trace` (search/route/model/stream/**memory** ← V2.1)
  - **미구현:** 세션·서비스 간 `trace_id` 체인
- **[L5-G6] Audit Trail** — Git commit / push / `.env` 제외
- **[L5-G7] Rule Feedback** — 모델 사고 누출 / 검색 판단 오판 / stream 호환
- **[L5-G8] Entropy / Drift Control** — 설정 꼬임 방지, OpenWebUI 볼륨 초기화 같은 기준점 회복

### [L5-O] Observability Dashboard *(V2.3 신설)*

> **목적:** 전체 스택이 커지면서 "지금 무엇이 살아있고, 얼마나 빠르고, 토큰을 얼마나 쓰고, 지식 파이프라인이 어디서 막혀 있는가"를 한 화면에서 본다. Semi Tech AI Hub 대시보드와 동급의 패널 4종(서비스 가용성 / 성능 / 자원 / 모델 소비) 지향.

**감시 범위 (4 범주):**

| # | 범주 | 주요 지표 | 수집원 |
|---|---|---|---|
| 1 | **서비스 헬스** | up/down, restart count, port, health endpoint | docker ps, 각 서비스 `/healthz`, 호스트 Ollama `/api/tags` |
| 2 | **LLM 메트릭** | 모델별 RPM·TPM, latency p50/p95, 토큰 in/out, 에러율 | L2 `iris_trace` (model/tokens/duration 필드 확장 필요) |
| 3 | **검색·메모리** | l4-search 호출수·실패율·평균 지연, memory bridge prefetch hit률·writeback 건수 | L2 trace + l4-search 로그 + iris-memory `/v1/events` |
| 4 | **L4-K 파이프라인** | K1 intake 큐 깊이(파일수), K2 처리율(/h), K2 실패 청크, Silver→Gold promote 대기수, _index.db 크기 | watchdog 로그 + Makefile job + `_index.db` 스냅샷 |

**구현 단계 (Phased):**

- **Phase 1 — 경량 자체 대시보드 (V2.3 즉시)**
  - 컴포넌트: `iris-observe` (FastAPI + 단일 HTML, 포트 `:18030`, memory-admin 패턴 차용)
  - 데이터원: 기존 `iris_trace` SQLite + 각 서비스 `/healthz` + jsonl 로그 tail
  - 패널: 서비스 헬스 배지 / 최근 100건 요청 latency 히스토그램 / 토큰 누적 카운터 / K1·K2 큐 깊이
  - 의존성: 신규 컨테이너 0 (FastAPI 1개만 추가)
  - 한계: 시계열 보존 짧음(=DB 보존기간), 알람 없음

- **Phase 2 — Trace 체인 + 메트릭 확장 (V2.4 예정)**
  - L5-G5 미구현 항목인 **세션·서비스 간 `trace_id` 체인** 완성 (X-Iris-Trace-Id 헤더 전파: WebUI → L2 → L4-S/Memory → Ollama)
  - `iris_trace` 스키마에 `prompt_tokens`/`completion_tokens`/`upstream_latency_ms`/`error_class` 추가
  - 패널에 모델별 토큰 소비 분포 + p95 latency 시계열 추가
  - 비용 컬럼 (모델별 단가 룩업) 옵션

- **Phase 3 — Prometheus + Grafana 승격 (스택 확장 시)**
  - 트리거 조건: 컨테이너 ≥8개, 또는 chunk ≥100k (sqlite-vec → Qdrant 마이그레이션과 동시)
  - 각 서비스 `/metrics` (prometheus_client) 노출, Grafana 컨테이너 추가
  - L5-O 자체 대시보드는 운영 요약 뷰로 유지, 상세는 Grafana로 위임
  - 알람(Alertmanager): 서비스 down / p95 임계초과 / K1 큐 적체 / Gold lint 실패

**디렉터리 (예정):**

```
iris-stack/iris-observe/
  app.py              # FastAPI 메트릭 수집 + 대시보드 SSR
  collectors/
    health.py         # /healthz 폴러
    trace.py          # iris_trace 집계
    pipeline.py       # _index.db / watchdog 큐 집계
  templates/dashboard.html
  Dockerfile
```

**스택 통합:** `docker-compose.yml`에 `iris-observe` 서비스 추가, `IRIS_OBSERVE_PORT=18030`, 읽기 전용 마운트로 `iris_trace.db`·`_index.db`·log dir 접근.

→

## [L6] Application Layer *(V2.3 재구조)*

> **V2.3 변경:** 단순 "Outputs/Products" 나열에서 **L4-K 소비 패턴별 4분류**로 재구조. 모든 응용단은 K5 Retrieval API 또는 매트릭스 조회로 L4-K와 연계.

### [L6-D] Domain Products — 도메인 제품

- **L6-D1 · L6-diagnosis (Diagnosis Tool V1.5)**
  - 위치: [diagnosis-tool/](diagnosis-tool/)
  - 자체 docker-compose, 자체 [llm_gateway/](diagnosis-tool/llm_gateway), `docker-compose project: diagnosis-tool-v15`
  - 데이터 계약: [docs/프로젝트문서/시스템설계/](diagnosis-tool/docs/프로젝트문서/시스템설계) (step4/step5/step6, contracts)
  - **L4-K 연계: K5-① 매트릭스 조회** (`industry/area/level`) — ch0~ch6 assemble 단계에서 호출
  - 상태: 🟡 자체 운영 중, L4-K 공급 대기

### [L6-R] Reports — 정형 산출물

- 보고서 / 설계서 / 검증 보고서 (대부분 미자동화)
- **L4-K 연계: K5-① 매트릭스 + K5-② 키워드** — 산업/주제 키워드 기반 자료 집계

### [L6-C] Conversational Surface — 대화 응답 회귀

- **L1 + L2가 L4-K를 조회하여 사용자에게 응답** (V2.3 신규 명시 연결)
- 트리거 키워드(예: "8산업 자료", 산업 코드, 영역명) 매칭 시 L2가 K5-① 또는 K5-③ 호출 → `[IRIS_KNOWLEDGE_CONTEXT]` 주입
- 현재: 미구현 (V2.3 신규 검토 항목)

### [L6-X] Future Products

- **L6-X1 · FMOS / IRIS OS** 후보
- **L6-X2 · 외부 채팅 채널 연동** (WeChat / Feishu / DingTalk / Slack)
- **L6-X3 · Working Local AI Assistant Baseline** (현재: OpenWebUI + L2 + Ollama + L4-S + Firecrawl 동작)

→

## [L7] Developer Tooling Layer *(V2.3 신설)*

> **V2.3 변경:** L4에 묻혀 있던 코딩·런타임·검증·스파이크를 **별도 보조 계층으로 분리**. 사용자 경로(L0→L1→L2→L4-K→L6) 외부에 위치, L4-K 자산 운영과 개발 흐름을 지원.

### [L7-C] Coding Gateway *(옛 L4-C)*

- **L7-C1 · iris-gateway**
  - 위치: [iris-gateway/](iris-gateway/)
  - 엔드포인트: `/task/ask`, `/task/code`, `/task/workflow`
  - LLM: Ollama 직결 (`qwen2.5:14b`, `qwen2.5-coder:14b` → 404 시 7b 폴백)
  - **L3-memory 라이브 연동** ([memory_client.py](iris-gateway/app/memory_client.py))
  - 상태: 🟡 analysis-only (패치 적용·테스트 실행 미구현)
- **L7-C2 · Cursor / IDE Bridge** — 외부 IDE
- **L7-C3 · Coding LLMs** — qwen2.5-coder:14b, qwen3-coder:30b
- **L7-C4 · Patch / Apply Flow** — 미구현
- **L7-C5 · Worktree Execution** — 미구현

### [L7-R] Runtime Ops *(옛 L4-R)*

- [iris-stack/docker-compose.yml](iris-stack/docker-compose.yml), [scripts/](iris-stack/scripts)
- 컨테이너 운영: open-webui / l2-gateway / l4-search / memory-admin
- 외부 의존: host Ollama / Firecrawl API

### [L7-V] Verification *(옛 L4-V)*

- 현재 수동: docker compose / docker logs / curl health / API 응답 검증
- 향후: 회귀 테스트 스크립트 자동화

### [L7-S] Spikes / Experiments

- **L7-S1 · L4-RS-spike (Firecrawl SDK v4)** — [L4-search/firecrawl-mcp/](L4-search/firecrawl-mcp), Node ESM CLI
- **L7-S2 · L1-ollamaui (실험)** — [L1-web-chat/ollama-ui/](L1-web-chat/ollama-ui), Ollama 직결 / Chrome extension 후보

역할: L4-K 자산 운영·개발 흐름 보조 (사용자 경로 외부)
**상태: 부분 라이브 (L7-C analysis-only, L7-R 운영, L7-V 수동, L7-S 검토)**

---

## LLM 모델 운영 정책 *(V2.3 신설 · 횡단 절)*

> **원칙:** 단일 거대 모델 대신 **용도별 특화 모델 다중 운영**. 사용자가 기다리는 경로(L2 채팅)는 큰 모델, 백그라운드 파이프라인(K2·K3)은 작은/특화 모델로 분리. 임베딩은 별도 모델 필수.

### 현 시점 권장 모델 매트릭스 (2026-05-15)

| # | 용도 | 호출 컴포넌트 | 권장 모델 | 사이즈 힌트 | 비고 |
|---|---|---|---|---|---|
| 1 | 채팅 응답 (사용자 대화) | [L2] L2_API | **qwen3** | 8B~14B | 한국어·다국어, 일반 추론 기본기 |
| 2 | 코딩 분석 | [L7-C] iris-gateway | **qwen3-coder** | 7B+ | 코드 컨텍스트·구조 인식 |
| 3 | 임베딩 (벡터화) | [L4-K K2] K2_Emb | **nomic-embed-text** | 137M, 768d | 로컬·빠름·다국어 OK |
| 4 | 자동 태깅 / 분류 | [L4-K K3] K3_Auto | **qwen3:4b** (소형) | 4B | 분류는 작은 모델로 충분, 처리량 우선 |
| 5 | 셀 lint / 모순 검증 | [L4-K K6] Lint | **qwen3** 재사용 | 8B~14B | 정확도 우선, 호출 빈도 낮음 |
| 6 | 보고서 / 장문 생성 | [L6-R] | **qwen3** 재사용 또는 외부 API | 14B+ | 품질 민감, 외부 모델 옵션 검토 |
| 7 | 검색 결과 요약 | [L2] (검색 트리거 시) | **qwen3** 재사용 | — | 채팅과 동일 컨텍스트 |
| 8 | 모니터링 / 관측 | [L5-O] iris-observe | **(LLM 미사용)** | — | 메트릭 집계 전용 |

### 연결 포인트 (puml 대응)

| 흐름 | 호출자 → Ollama | 엔드포인트 | 경유 정책 |
|---|---|---|---|
| #1 채팅 | `L2_API --> Ollama` | `/api/chat` | 사용자 trace에 모델·토큰 메타 기록 |
| #2 코딩 | `L7C ..> Ollama` | `/api/generate` | L7 자체 trace, L5-O Phase2에서 통합 |
| #3 임베딩 | `K2_Emb ..> Ollama` | `/api/embeddings` | 파이프라인 직결 (L2 우회) |
| #4 태깅 | **`K3_Auto ..> Ollama` (신규)** | `/api/generate` | 파이프라인 직결, 소형 모델 고정 |
| #5 lint | **`Lint ..> Ollama` (선택)** | `/api/generate` | 큐레이션 시점 수동 트리거 |

### 라우팅·관측 원칙

- **L2 경유 vs 직결 판단 기준:**
  - 사용자 응답 = **L2 경유** (trace·rate limit·context injection 통합)
  - 내부 파이프라인 (임베딩·태깅·lint) = **직결** (사용자 trace 오염 방지, 처리량 우선)
- **trace_id 헤더 전파 (L5-O Phase2):** 직결 호출에도 `X-Iris-Trace-Id`를 실어 관측 통합
- **모델 상주 정책:** Mac Ollama VRAM 제약 — 항상 상주(qwen3, nomic-embed-text), 온디맨드(qwen3-coder, qwen3:4b)
- **L5-O 토큰 패널은 모델별 칼럼**으로 분리, 비싼 용도 식별 후 모델 교체 가능

### 모델 교체 게이트

- 임베딩 모델 변경 = **전체 재인덱싱 필요** (K2 청크 vec 컬럼 재생성). 변경 전 영향 평가 필수.
- 채팅 모델 변경 = trace 메타만 바뀜, 무중단.
- L5-O Phase2 토큰 비용 데이터 기반으로 분기별 재검토.

---

## 2026-05-15 기준 실제 구현 맵

```
/Users/iris/Documents/0Dev/                    ← V2.0의 /Users/iris/0Dev/ 정정
├── ARCHITECTURE.md                            ← 인덱스 문서 (V2.1)
├── _layers/                                   ← 계층 코드 심볼릭 링크 (V2.3 코드명 갱신)
│   ├── L0-stack         → ../iris-stack
│   ├── L1-claw          → ../iris-claw
│   ├── L1-ollamaui      → ../L1-web-chat
│   ├── L2-gateway       → ../iris-stack/l2-gateway
│   ├── L3-memory        → ../iris-memory
│   ├── L4-S-search      → ../iris-stack/l4-search       (옛 L4-RS-search)
│   ├── L4-K-knowledge   → ../iris-system                ★ 무게중심
│   ├── L6-D-diagnosis   → ../diagnosis-tool             (옛 L6-diagnosis)
│   ├── L7-C-gateway     → ../iris-gateway               (옛 L4-C-gateway)
│   └── L7-S-spike       → ../L4-search                  (옛 L4-RS-spike)
│
├── iris-stack/                                ← L0-stack
│   ├── docker-compose.yml
│   ├── l2-gateway/                            ← L2
│   ├── l4-search/                             ← L4-RS
│   ├── memory-admin/                          ← L3-A1
│   ├── memory-profiles/                       ← L3-P1
│   └── scripts/
│
├── iris-memory/                               ← L3
│   ├── app/{routers,services,models,schemas}
│   ├── docker-compose.yml                     (포트 8001)
│   └── data/memory.db
│
├── iris-system/                               ← L4-K ★
│   ├── apps/{router,wiki}/
│   ├── knowledge/
│   │   ├── raw/                              [K4 Bronze] (불변)
│   │   │   ├── files/    (K1a)
│   │   │   ├── clips/    (K1b)
│   │   │   └── inbox/    (K1c, 격리)
│   │   ├── staging/                          [K4 Silver] (재생성 가능)
│   │   ├── wiki/                             [K4 Gold] (Obsidian vault, git)
│   │   │   ├── _templates/
│   │   │   ├── industries/{A..H}_*/
│   │   │   ├── areas/   (계획·품질·설비·물류)
│   │   │   ├── concepts/
│   │   │   └── sources/
│   │   ├── _index.db                         (SQLite + FTS5 + sqlite-vec)
│   │   ├── CLAUDE.md / IRIS_WIKI_QUALITY_RULES.md
│   │   └── watchlist.yaml                    (K1c 설정)
│   ├── Makefile                              (오케스트레이션 · K1~K6 전반)
│   └── storage/sqlite/                       (V2.0 호환 잔존)
│
├── iris-gateway/                              ← L7-C (옛 L4-C)
│   ├── app/{llm_client,memory_client,route_engine,...}
│   └── logs/{task_runs,errors,memory_events}.jsonl
│
├── iris-claw/                                 ← L1 (정식 후보)
│   ├── openclaw-workspace/{IDENTITY,SOUL,MEMORY,SKILLS,TOOLS}.md
│   └── tools/search/search_web.py             (Tavily)
│
├── L1-web-chat/ollama-ui/                     ← L7-S2 (실험)
├── L4-search/firecrawl-mcp/                   ← L7-S1 (옛 L4-RS-spike)
└── diagnosis-tool/                            ← L6-D1
    ├── docker-compose.yml (project: diagnosis-tool-v15)
    ├── llm_gateway/
    ├── contracts/
    └── docs/
```

---

## 현재 서비스 연결 구조 (실측, 2026-05-15)

```
[Browser]
   │
   ├── http://localhost:3000  ────► [L1-webui · OpenWebUI]
   │                                       │  OpenAI-compat
   │                                       ▼
   │                              http://l2-gateway:8010/v1/chat/completions
   │                                       │
   │                              ┌────────┴───────────┐
   │                              ▼                    ▼
   │                  일반질문                    검색질문
   │                  Ollama (host:11434)         L4-search:8020/search
   │                                                  │
   │                                              Firecrawl
   │                                                  │
   │                                              결과 → L2 context
   │                                                  │
   │                                              Ollama 호출
   │                                                  │
   │                                              응답 + [IRIS 검색 출처]
   │
   ├── (실험) http://localhost:8000  ──► [L1-ollamaui]  ──직결──► Ollama:11434
   │                                                              (L2 우회)
   │
   ├── (보류 와이어링) [L1-claw / OpenClaw]  ──자체 L2(직접 LLM + Tavily)──
   │                                          (L2-gateway 미경유, stack 미연결)
   │
   └── (별도) [L4-C-gateway · iris-gateway]
          /task/ask|code|workflow
              │
              ├── Ollama (qwen2.5/qwen2.5-coder)
              └── L3-memory (8001)  prefetch / writeback  ◄── 라이브 ✅

[L3-memory 단독]                       [L4-K-knowledge 단독]
  iris-memory:8001                       iris-system (raw → wiki → sqlite)
  ▲                                      ▲
  │ RO mount                             │ ※ 외부 노출 라우트 검토 필요
  │
  memory-admin:18020 (RO viewer)

[L6-diagnosis 단독]
  diagnosis-tool-v15 (자체 compose, 자체 llm_gateway)
  ※ L4-K 공급 대기
```

**핵심 미연결:**
1. L1-claw ↔ L0-stack
2. L4-K-knowledge ↔ L1/L2 (질의 경로)
3. L4-K-knowledge ↔ L6-diagnosis (공급 경로)
4. L2 ↔ L3-memory (코드 OK, env 토글)

---

## L4-K 중심 재정렬 (V2.3 다음 단계)

V2.2에서 L4-K 내부 골격을, **V2.3에서 K1~K6 sub-layer와 L6 4종 소비자 + L7 분리**까지 구조 확정. 다음 단계는 코드명 마이그레이션 + 구현 1차 사이클:

1. 🔴 **L4-K 스켈레톤 생성 (최우선)**
   - `knowledge/{raw/{files,clips,inbox},staging,wiki/{industries,areas,concepts,sources,_templates}}` 폴더 + Makefile 골격
   - `_index.db` 스키마 생성 (documents, documents_fts, chunks, chunk_vec)
   - K3 frontmatter 필수 필드 (`industry/area/level/status/trust/sources`) pydantic 모델
2. 🔴 **K1a Document Drop 우선 (Lane A)**
   - `raw/files/` watchdog + unstructured 추출 → K2 → K4 적재
   - 사용자 보유 PDF/PPT 1개로 end-to-end 검증
3. 🔴 **첫 Gold 셀 3~5개로 K6 본문 스키마 발견**
   - 예: B산업·품질·L3 / H산업·계획·L2 — K5-③ 의미검색으로 관련 청크 → 사람이 Gold 정제
   - 셀 3~5개 쓰고 공통 본문 구조 추출 → 템플릿 확정
4. 🔴 **계층 코드 마이그레이션 (V2.3 신규)**
   - `_layers/` 심볼릭 링크 갱신: L4-RS → L4-S, L4-C → L7-C, L4-RS-spike → L7-S, L6-diagnosis → L6-D1
   - ARCHITECTURE.md 인덱스도 동기화
5. 🟡 **L6-D1 ↔ K5 데이터 계약**
   - K5-① 매트릭스 쿼리 (`industry/area/level`) → diagnosis-tool ch1~ch6에서 시험 호출
   - 연결: read-only mount 또는 HTTP (memory-admin ↔ iris-memory 패턴)
6. 🟡 **K1b Quick Clip (Lane B)** — L4-S(Firecrawl) 재사용, `iris clip <url>` CLI 또는 Obsidian Web Clipper
7. 🟡 **L6-C 검토** — L2가 K5 호출하여 채팅 응답에 지식 컨텍스트 주입 (`[IRIS_KNOWLEDGE_CONTEXT]`) 가능성
8. 🟡 **L1-claw 자체 L2 제거 → L2-gateway 통일** (V2.1에서 이월)
9. 🟢 **K1c Watch List** — wiki 큐레이션 루틴 잡힌 뒤에만. watchlist.yaml + cron, 산업당 최대 10건/주, 30일 미검토 archive
10. ⏳ **L5 trace_id 체인** (V2.1에서 이월 → L5-O Phase2에 통합)
11. ⏳ **벡터 백엔드 이주** — 100k 청크 신호 시 Qdrant single (VectorStore 인터페이스 교체, L5-O Phase3와 동기화)
12. 🔴 **L5-O Observability Phase1 (V2.3 신규)** — `iris-observe:18030` FastAPI 단일 컨테이너, 4범주 패널(헬스/LLM/검색·메모리/K파이프라인), 신규 의존성 0

---

## 한 줄 핵심 요약

> **2026-05-15 V2.3 기준 IRIS의 중심은 L4-K 지식센터(iris-system)이며,
> 내부는 K1 Intake → K2 Cleansing → K3 Classify → K4 Store ↔ K5 Search ← K6 Curate의 6단계 lifecycle로 가시화되었다.
> L4는 정보 서비스(L4-S Search · L4-K Knowledge)로 좁혀졌고, 코딩·런타임·검증·스파이크는 성격 차이로 L7 Developer Tooling으로 분리되었다.
> L6 응용단은 D(도메인)·R(보고서)·C(대화)·X(미래) 4종으로 분류되어 K5 Retrieval API와 명시적으로 연계된다.
> 다음 마일스톤은 K1a Document Drop으로 첫 Bronze→Silver→Gold 사이클을 닫고, L6-D1 diagnosis에 K5-① 매트릭스 셀 1개를 공급하는 것이다.**
