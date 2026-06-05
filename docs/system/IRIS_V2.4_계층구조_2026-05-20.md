# IRIS V2.4 계층 구조 — 2026-05-20 기준

> **버전:** 2.4 (rev 5 — **K4 스키마·K5 API 1차 구현**, **K1d Reference Lane 신설**, **K6 Quartz 보조 도구 좌정**, 산업 폴더 canonical 표준화)
> **이전 버전:** V2.3 (2026-05-15, K1~K6 sub-layer 명시), V2.2 (3-Lane 확정), V2.1, V2.0
> **상태:** L4-K K4 스키마 + K5-① 매트릭스 + K5-② FTS **라이브 ON** (630 docs / reference lane). 첫 Gold 셀 패턴 발견은 여전히 보류.
> **무게중심:** **L4-K 지식센터(iris-system).** V2.3에서 확립된 K1~K6 골격에 실데이터·코드 1차 채움.

---

## V2.3 → V2.4 핵심 변경 (5일간 실작업)

| # | 항목 | V2.3 (2026-05-15) | V2.4 (2026-05-20) |
|---|---|---|---|
| 1 | **K4 `_index.db` 스키마** | "스켈레톤 생성 (최우선)" | ✅ [apps/ingest/schema.sql](iris-system/apps/ingest/schema.sql) 작성·운영 (documents/documents_fts/chunks/meta_kv) |
| 2 | **K5 Retrieval API** | "L6-D1 ↔ K5 데이터 계약" 🟡 대기 | ✅ `query_matrix` + `query_fts` ([apps/wiki/retrieval.py](iris-system/apps/wiki/retrieval.py)) |
| 3 | **K1 Intake — Lane 확장** | K1a/K1b/K1c (Bronze 3-Lane) | **+ K1d Reference Lane 신설** (외부 canonical 무복사 등록, `lane='reference'`) |
| 4 | **첫 대규모 인덱싱** | 0건 (스켈레톤만) | **630 documents** (8산업 × ~6 area + ~25 catalog kinds, diagnosis-tool/server/data 출처) |
| 5 | **첫 Gold 셀** | "3~5개로 K6 본문 스키마 발견" 🔴 | 🟡 미착수 (V2.4에서도 이월) |
| 6 | **L6-D1 ↔ K5 계약** | 🟡 대기 | 🟡 **path-pointer 패턴 확립** (K5 doc.path → diagnosis-tool/server/data, no copy). diagnosis-tool 자체는 미접속 |
| 7 | **K6 저작 도구** | Obsidian vault 단독 | **+ Quartz v4 보조 도구** (`apps/quartz/`, content symlink, K6 산하 발행 도구 — 계층 확장 아님) |
| 8 | **산업 폴더명 표준화** | `knowledge/wiki/industries/{A..H}_*/` (자유 명명) | **canonical 코드 채택** (`A_project_eto_ato`, `B_semiconductor_fab_backend`, …, `H_auto_mobility` — diagnosis-tool/server/data/industry_master.json 정본) |
| 9 | **sqlite-vec / K5-③ semantic** | "100k 청크 신호 시 Qdrant" — sqlite-vec 1차 사용 가정 | 🔴 **잠정 유예** — macOS system Python `enable_load_extension` 미지원으로 chunk_vec 테이블 비활성화. K5-③ 의미검색 본격 도입은 Python 빌드 교체 또는 Ollama 직결 임베딩+외부 인덱서로 우회 검토 |
| 10 | **다이어그램 도구** | 없음 | Mermaid 기반 다이어그램 스킬 추가 (`~/.claude/skills/diagram/`, CLI `mmdc`) — V2.x 계층 외부, 문서 작성 보조 |
| 11 | **메모리/auto memory** | 별도 운영 | Claude auto-memory에 IRIS center-of-gravity·계층 코드·iris-claw 스택·Quartz 좌정 6건 기록 (Claude 보조 메모리, V2.x 사양 외) |

---

## 새로 도입된 개념

### K1d Reference Lane — 외부 canonical 무복사 등록 *(V2.4 신규)*

**문제:** diagnosis-tool/server/data/ 80개 JSON은 산업 정본인데, K1a~K1c Bronze 파이프라인에 태우려면 (1) 복사·소유권 충돌, (2) K2 클렌징 무의미(이미 정제됨), (3) K4 Promotion Gate(사람 검수)가 자동 운영을 막음.

**해결:** **lane='reference'** 신설 — Bronze/Silver/Gold 3-Tier 외부에 위치, K1 Intake의 4번째 차선.

| 항목 | K1a Document Drop | K1b Quick Clip | K1c Watch List | **K1d Reference (신규)** |
|---|---|---|---|---|
| 위치 | `raw/files/` | `raw/clips/` | `raw/inbox/` | **(외부 경로, path-pointer만)** |
| 트리거 | 폴더 투입 | URL 1개 | cron | `make ingest-reference` |
| 신뢰도 | ★★★ verified | ★★ clipped | ★ auto | **★★★ verified** (정본) |
| K2 클렌징 | 적용 | 적용 | 적용 | **미적용** (이미 구조화) |
| K4 Promotion | Bronze→Silver→Gold | 동일 | 동일 | **별도 lane, 승격 없음** |
| 본문 저장 | 원본 파일 + chunks | 동일 | 동일 | **chunks만 (path는 외부 정본)** |
| Idempotency | mtime+hash | 동일 | 동일 | `DELETE WHERE lane='reference'` + 전량 재삽입 |

**원칙:**
- **No copy**: `documents.path`는 절대경로(`/Users/iris/Documents/0Dev/diagnosis-tool/server/data/...`)만 저장. 본문은 K5-② FTS용으로만 chunks에 평탄화.
- **Read-only contract**: 인덱서는 diagnosis-tool 디렉터리에 절대 쓰지 않음.
- **K5에서 동등 노출**: `query_matrix(industry='B', area='ch2_stack')` 등 매트릭스 키로 조회 가능. 호출자는 `path`를 받아 원본 JSON 직접 파싱.

### Quartz v4 — K6 산하 발행 도구 *(V2.4 신규 좌정)*

- 위치: [iris-system/apps/quartz/](iris-system/apps/quartz/), `content/` → `../../knowledge/wiki` 심볼릭
- **계층이 아니다.** K6 Curate의 _저작 도구_ Obsidian 옆에 _발행 도구_로 좌정. V2.3 계층은 변경 없음.
- 용도: Gold lane 정적 사이트 발행 (그래프뷰·검색·wikilink). 외부 공유 채널은 미정.
- V2.x 사양 외부 도구 — 추후 제거되어도 K4/K6 본체는 무영향.

---

## K4 스키마 (V2.4 확정본, 운영 중)

V2.3에서 명세된 형태에서 1차 실구현:

```sql
CREATE TABLE documents (
  doc_id      TEXT PRIMARY KEY,
  path        TEXT NOT NULL,
  lane        TEXT NOT NULL,          -- bronze | silver | gold | reference (V2.4 신규)
  trust       TEXT NOT NULL DEFAULT 'verified',
  industry    TEXT,                   -- A..H or NULL
  area        TEXT,                   -- ch1_mgmt_model | ch2_stack | ... | catalog:<kind>
  level       TEXT,                   -- S/M/L | default | sub-code
  title       TEXT,
  source_url  TEXT,
  fetched_at  TEXT,
  promoted_to TEXT
);
CREATE INDEX idx_doc_matrix ON documents(industry, area, level);
CREATE INDEX idx_doc_lane   ON documents(lane);

CREATE VIRTUAL TABLE documents_fts USING fts5(
  title, body, content='', tokenize='unicode61'
);

CREATE TABLE chunks (
  chunk_id TEXT PRIMARY KEY,
  doc_id   TEXT NOT NULL REFERENCES documents(doc_id),
  ord      INTEGER NOT NULL,
  text     TEXT NOT NULL
);

-- chunk_vec: V2.3에서 예고했으나 macOS system Python 제약으로 V2.4 비활성화
-- CREATE VIRTUAL TABLE chunk_vec USING vec0(embedding FLOAT[768]);

CREATE TABLE meta_kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
```

**V2.3 명세 대비 차이:** `chunk_vec` 잠정 미생성. 그 외 동일.

---

## K5 Retrieval API (V2.4 1차 구현)

| 함수 | 패턴 | 시그니처 | 상태 |
|---|---|---|---|
| `query_matrix` | K5-① 결정적 매트릭스 | `(industry, area, level, lane='reference', limit=50)` | ✅ |
| `query_fts` | K5-② FTS5 키워드 | `(text, industry, area, lane='reference', limit=20)` | ✅ |
| (미구현) | K5-③ 의미 검색 | `(text, ...)` → vec L2 distance | 🔴 sqlite-vec 잠정 유예 |

- 구현: [apps/wiki/retrieval.py](iris-system/apps/wiki/retrieval.py)
- 호출자 후보: L6-D1 (diagnosis-tool ch1~ch6 assemble), L2-gateway(`[IRIS_KNOWLEDGE_CONTEXT]` 주입), L6-R 보고서
- **현재 호출자 0개** — API 노출(HTTP)은 다음 마일스톤

---

## L4 영역 갱신 (V2.3 구조 유지, 내용 보강)

### [L4-K] Knowledge Center — sub-layer 상태

| Sub-layer | V2.3 상태 | V2.4 상태 |
|---|---|---|
| **K1 Intake** | 3-Lane 명세 | **+K1d Reference Lane 운영** (630 docs 적재) / K1a~K1c 골격만 |
| **K2 Cleansing** | 명세 | 미구현 (K1d는 K2 우회) |
| **K3 Classify** | 매트릭스 좌표계 정의 | 매트릭스 키(`industry/area/level`)가 K1d 인덱싱에 적용·검증됨 |
| **K4 Store** | 스키마 설계 | ✅ **운영 중** (lane=reference 630건) |
| **K5 Search** | API 명세 | ✅ **①·② 1차 구현**, ③ 유예 |
| **K6 Curate** | Obsidian | + Quartz 발행 도구, 산업 폴더 canonical 표준화 |

### [L4-S] Search Service — 변경 없음

V2.3 그대로. Firecrawl + l4-search:8020.

---

## L6 응용단 — K5 첫 소비 패턴 (V2.4)

| L6 | V2.3 명시 연계 | V2.4 실상 |
|---|---|---|
| **L6-D1 diagnosis** | K5-① 매트릭스 (대기) | K5 doc.path = diagnosis-tool/server/data 원본 — **path-pointer만 일치**, HTTP 미연결. diagnosis는 여전히 자체 server/data 직접 읽음 |
| **L6-R reports** | K5-①·② | 미접속 |
| **L6-C 대화** | K5-① 또는 ③ → L2 context 주입 | 미접속 |
| **L6-X** | 미래 | 미래 |

---

## 다음 단계 (V2.5 후보)

1. 🔴 **첫 Gold 셀 3~5개로 K6 본문 스키마 발견** — V2.3에서 이월. K5-② FTS가 살아있으니 reference lane에서 관련 청크 찾기 가능 → Gold 셀 손으로 작성 → 본문 템플릿 추출.
2. 🔴 **K5 HTTP 노출** — `query_matrix` / `query_fts`를 FastAPI 라우터로 wrap. L2-gateway에서 `[IRIS_KNOWLEDGE_CONTEXT]` 주입 PoC.
3. 🔴 **L6-D1 ↔ K5 HTTP 계약** — diagnosis-tool ch1~ch6 중 1개를 K5 호출로 전환 (현재는 server/data 직접 읽기).
4. 🟡 **K1a Document Drop** — 사용자 PDF/PPT 1개 end-to-end (V2.3에서 이월).
5. 🟡 **K5-③ semantic 우회안** — sqlite-vec 대안: (a) Python 빌드 교체 (pyenv + `--enable-loadable-sqlite-extensions`), (b) Ollama embeddings + FAISS/Qdrant 별도 인덱스, (c) 임베딩 보류하고 K5-② FTS만으로 V2.5 살아가기. ROI 평가 필요.
6. 🟡 **K1d Reference Lane 확장** — diagnosis-tool 외 다른 정본(예: ARCHITECTURE.md, V2.x 시리즈) 등록 검토.
7. 🟢 **L5-O Observability Phase1** — V2.3에서 이월.
8. 🟢 **L1-claw ↔ L2-gateway 통일** — V2.1 → V2.3 이월 → V2.5.
9. ⏳ **L5 trace_id 체인** — L5-O Phase2 통합.

---

## 한 줄 핵심 요약

> **2026-05-20 V2.4 기준 IRIS는 V2.3에서 그린 K1~K6 골격의 K4(스토어)·K5(검색 ①②)를 처음으로 실데이터로 채웠다.
> diagnosis-tool/server/data 80개 JSON을 무복사로 K4 `_index.db`에 630건 등록(신규 lane='reference')하고, K5-① 매트릭스·K5-② FTS 함수를 1차 노출했다.
> 그러나 K6 Gold 셀은 여전히 0건이고 L6-D1과의 HTTP 계약은 미연결이라, V2.5의 최우선은 (a) 첫 Gold 셀 3~5개로 본문 스키마 발견과 (b) K5 HTTP 노출 + 첫 소비자 1개 연결이다.
> sqlite-vec 제약으로 K5-③ semantic은 잠정 유예 — 임베딩 백엔드 우회안을 V2.5에서 결정한다.**
