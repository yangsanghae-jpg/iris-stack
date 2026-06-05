# IRIS V2.5 아키텍처 명세 및 실전 가동 안

- **버전:** 2.5 (rev3 최종 확정본)
- **확정일:** 2026-05-22
- **이전 버전:** V2.4 (2026-05-20, Reference Lane 신설 및 630 docs 인덱싱 완료)
- **상태:** L4-K 지식센터 기반 데이터 파이프라인 동맥경화 해소 / 결함 추적·측정 사양 완결 / 실전 가동 라이브
- **무게중심:** 주인(설계자)의 하향식 통제권 아래, 정량화된 수치와 호출자 식별 규약으로 결함을 *드러내는* 실질적 가치 검증

---

## 0. 개정 요약 (rev1 → rev2 → rev3)

| 회차 | 주요 변경점 |
|---|---|
| rev1 | K5 HTTP 엔드포인트 개방, L6-D1 계약 전환, K6 Gold 셀 템플릿 확립, 세만틱 검색 우회(Ollama+FAISS) |
| rev2 | 단일 통합 Retrieval 엔드포인트, L1 통제권 복원, Gold 정량 트리거, L6-D1 Fallback, Telemetry Zero |
| **rev3** | **측정 정의 구체화(코사인 ≥ 0.80, distinct doc_id 5), 호출자 식별 헤더(`X-IRIS-Caller`) 규약, 위장 Fallback 알람(10%/100건 윈도우), 라우팅 휴리스틱 확정, V2.6 의존성 명시, 로그 회전·완료 기준 추가** |

---

## 1. V2.4 결점 진단 (V2.5 가 풀어야 할 4대 병목)

1. **실질적 소비자의 부재** — K5 Retrieval API 구현되었으나 호출자 0개. L6-D1은 여전히 `server/data/` 직접 파싱.
2. **Gold 셀 발견 지연** — `lane='gold'` 0건 이월. 큐레이션 단계 진입 실패.
3. **세만틱 검색 마비** — macOS 시스템 Python 제약으로 `sqlite-vec` 비활성. 키워드(FTS5) 의존 한계.
4. **주변부 도구 조기 좌정** — Gold 부재 상태에서 Quartz v4 결합 시도, 리소스 분산 우려.

---

## 2. 타겟 아키텍처 개관

```
[K1 Intake] ──▶ [K4 Store (_index.db)] ──▶ [K5 Retrieval API] ──▶ [L6 응용단 / 검증]
 K1a~c 사용자      documents (Metadata)       /api/v1/retrieval        L6-D1 (Sandbox 고객)
 K1d 외부 정본     chunks    (FTS5)             ↳ mode=auto            L2-gateway (대화 컨텍스트)
 (No-Copy)         FAISS+Ollama (Semantic)      ↳ mode=matrix|fts|     L6-R    (보고서)
                            ▲                          semantic
                            │ 큐레이션 승격         ↓
                       [K6 Curate]           [L5 Telemetry Zero]
                       Gold 정량 트리거         iris_k5_telemetry.log
                       (A/B/C)                       │
                                                     ▼
                                              [L1 주인 / 통제단]
                                              · 알람 수신
                                              · 정책 결정
```

### 2.1 3대 핵심 원칙
- **의존성 단방향화** — L6는 K5 API 를 통해서만 데이터에 접근. 로컬 정본 직접 파싱은 *Fallback 경로에서만* 허용.
- **No-Copy Contract** — `lane='reference'` 원본 소유권은 외부(diagnosis-tool)에 존속. 내부 인덱스는 read-only path-pointer.
- **하이브리드 검색 단일화** — Matrix / FTS / Semantic 세 모드를 단일 엔드포인트(`/api/v1/retrieval`)에서 자동 라우팅.

---

## 3. 레이어 성격 재정의 (L1 통제권 복원)

| 코드 | 역할 | V2.5 에서의 포지션 |
|---|---|---|
| **L1** Interface / 통제단 | 주인(설계자)의 전권 제어 계층 | 하향식 프롬프트 통제 + L5 로그·알람 수신 |
| **L2** Gateway / 중계단 | 통제 명령 → 컨텍스트 결합 | `/retrieval/semantic` 결과를 `[IRIS_KNOWLEDGE_CONTEXT]`로 주입 |
| **L4-K** Knowledge Center | 코어 자산 (메타·청크·벡터) | K1~K6 sub-layer 완결 |
| **L5** Observability / 감시단 | Telemetry Zero + 임계치 알람 | K5 내부 파일 append + L1 이벤트 |
| **L6** Application / **검증단** | **목적이 아니라 1차 검증용 Sandbox 고객** | K5 데이터 계약을 실전 비즈니스 로직에서 두드려 보는 테스트베드 |

> ⚠️ **L6는 마일스톤의 *목적*이 아니다.** V2.5 의 성공 여부는 D1 의 동작이 아니라, *D1 을 통해 K5 계약의 결함이 드러나는가*로 판단한다.

---

## 4. L4-K 지식센터 sub-layer 명세

### 4.1 K1 Intake
- **K1a~K1c (Bronze 3-Lane)** — 사용자 Drop · 외부 수집 · 가공 스트림. (V2.5 에서는 골격 유지)
- **K1d Reference Lane (No-Copy)** — `lane='reference'` 정본의 절대경로 + 최소 청크 텍스트만 동기화.

### 4.2 K2 Cleansing
- 비정형(K1a~c) → 클렌징 파이프라인 필수 통과.
- **K1d Reference → K2 우회.** 이미 구조화된 정본이므로 효율 극대화.

### 4.3 K3 Classify
- 8대 산업 표준 정본 코드 (`A_project_eto_ato` ~ `H_auto_mobility`).
- 매트릭스 키 `(industry, area, level)` ↔ K4 documents 인덱스 필드 1:1 동기화.

### 4.4 K4 Store — 하이브리드 DB 스키마

```sql
CREATE TABLE documents (
  doc_id      TEXT PRIMARY KEY,
  path        TEXT NOT NULL,           -- reference 라인은 외부 절대경로 유지
  lane        TEXT NOT NULL,           -- bronze | silver | gold | reference
  trust       TEXT NOT NULL DEFAULT 'verified',
  industry    TEXT,                    -- A..H
  area        TEXT,                    -- ch1_mgmt_model | ch2_stack | ...
  level       TEXT,                    -- S/M/L | default
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

CREATE TABLE meta_kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
```

> Vector store 는 SQLite 외부에 분리: **Ollama 임베딩 + 로컬 FAISS 인덱스**. macOS 시스템 Python 의 `sqlite-vec` 제약 우회.

---

## 5. K5 단일 통합 Retrieval API

### 5.1 단일 엔드포인트
```
GET /api/v1/retrieval
    ?mode=auto|matrix|fts|semantic
    &query=<text>
    &industry=<A..H>
    &area=<ch?_*>
    &level=<S|M|L|default>
    &lane=<reference|bronze|silver|gold>
    &limit=<int, default 20>
```

### 5.2 호출자 식별 헤더 규약 (Caller Identity)

| 호출 주체 | 헤더 값 |
|---|---|
| L6 진단 엔진 | `X-IRIS-Caller: L6-D1` |
| L2 게이트웨이 대화단 | `X-IRIS-Caller: L2-Gate` |
| L6 보고서 생성기 | `X-IRIS-Caller: L6-R` |

- 헤더 누락 호출은 Telemetry 에서 **`FAULT:anonymous`** 로 마킹되어 감시망에 노출된다. (조용한 `unknown` 처리 금지)

### 5.3 자동 라우팅 휴리스틱 (`mode=auto` 또는 누락 시)

1. **1순위 Matrix** — `query` 비어 있고 `(industry, area)` 완비 → 결정적 path-pointer 반환.
2. **2순위 FTS** — `query` 에 `"..."` 구문 검색 또는 FTS 연산자(`AND`/`OR`/`NOT`) 포함 → `documents_fts` 매칭.
3. **3순위 Semantic** — 위 둘에 걸리지 않는 자연어 질의 → Ollama 임베딩 + FAISS L2 거리.

> 명시 호출(`mode=fts` 등)은 휴리스틱을 우회한다. 비용 순(Matrix < FTS < Semantic)으로 분기하여 평균 응답시간 최적화.

---

## 6. K6 Curate — Gold 셀 정량 트리거

> **양식(Gold Cell Spec) 정의 및 Quartz v4 발행은 V2.6 으로 이월.** V2.5 는 *후보군 자동 식별* 까지만 책임진다.

### Trigger A — 교차 참조 임계치
- 동일 `(industry, area)` 내에서, K1d Reference 의 특정 지식 개체가 **distinct `doc_id` 5개 이상**의 청크에서 인용·매칭될 때.
- 단일 문서 내 복수 청크 중복 인용은 1건으로 산정 (데이터 왜곡 방지).

### Trigger B — 컨텍스트 동시 출현
- `lane='bronze'` 청크와 K1d 정본 텍스트 간 **Ollama `nomic-embed-text` 모델 기준 코사인 유사도 ≥ 0.80** 동시 플래그.
- ⚠️ **의존성:** K1a 비정형 E2E 파이프라인은 V2.6 항목. **V2.5 에서 Trigger B 카운트 0 은 설계된 정상 상태.**

### Trigger C — L6-D1 실행 기반 히트
- L6-D1 진단 엔진이 K5 호출 결과의 특정 `doc_id` 를 **진단 룰 도출에 1회 이상 실제 사용**한 경우.
- HTTP 200 + 비어있지 않은 응답만으로는 부족 — *룰 엔진의 사용 흔적*까지 요구하여 Gold 품질 보장.
- Trigger C 의 입력원은 **L5 Telemetry Zero 로그**. ⇒ 자생적 Gold 발견 루프 형성.

---

## 7. L6-D1 회복력 계약 (Embedded Fallback)

### 7.1 3단 가동 체계
```
[L6-D1 가동]
    │
    ▼  TRY
[K5 HTTP 호출]
    │
    ├─ 성공 ──▶ Telemetry: fallback_flag=false
    │
    └─ 실패 / 타임아웃 ──▶ FALLBACK
                              │
                              ├─ 로컬 server/data 직접 파싱 (가용성 확보)
                              ├─ Telemetry: fallback_flag=true
                              │
                              └─ 🚨 caller_identity 별 최근 100건 중 fallback 비율 ≥ 10%
                                          │
                                          └─▶ L1 (주인) 즉시 알람
                                              · 터미널 경고 세션
                                              · 이벤트 에러 레이즈
```

- **Embedded 모드**: `IRIS_K5_MODE=embedded` 환경 변수 시 K5 모듈을 라이브러리로 import → HTTP 서버 없이 D1 단독 테스트 가능.
- **위장 성공(Silent Failure) 차단**: Fallback 은 *임시 피난처*. 정상 상태로 위장될 수 없도록 비율 알람으로 강제.

### 7.2 알람 윈도우 정책
- **호출자별 독립 집계** — `caller_identity` 별로 최근 100건 윈도우를 따로 유지. (L6-D1 의 fallback 과 L2-Gate 의 fallback 은 의미가 다르다)
- 임계치 도달 시 일회성 알람이 아니라, **해당 caller 의 비율이 임계치 아래로 복귀할 때까지 재발화 억제(쿨다운 5분)** 후 재평가.

---

## 8. L5 Telemetry Zero — 최소 관측성

### 8.1 로그 레코드 포맷
```
[TIMESTAMP] | CALLER_ID | ROUTING_MODE | HIT_COUNT | RESPONSE_TIME_MS | FALLBACK_FLAG
```
- Single-line text append, K5 라우터 처리 완료 시점에 1건 기록.

### 8.2 파일 회전 정책
- **일자 기반 회전** — `iris_k5_telemetry.YYYY-MM-DD.log` 자정 롤오버.
- **크기 안전망** — 단일 파일 50MB 초과 시 시퀀스 분할 (`...2026-05-22.1.log`).
- 14일 경과 파일은 `gzip` 압축, 90일 경과 파일은 자동 폐기.

### 8.3 피드백 루프
- 알람 → L1 (주인) 직접 통지.
- Trigger C 입력 → K6 Curate.
- 단순 append 한 줄이 *운영 감시 + Gold 발견 + 결함 고발* 세 역할을 동시 수행.

---

## 9. L6 응용단 인터페이스 계약

| 컴포넌트 | V2.4 (AS-IS) | V2.5 (TO-BE) |
|---|---|---|
| **L6-D1** diagnosis | `server/data/` JSON 직접 파싱 | `/api/v1/retrieval?mode=matrix` 호출, path-pointer 사용. Fallback 시에만 로컬 파싱. |
| **L6-R** reports | 미접속 | `/api/v1/retrieval?mode=fts` 키워드 청크 수집 후 보고서 자동 템플릿 |
| **L6-C** 대화 컨텍스트 | 미접속 | L2-Gateway 결합. `/api/v1/retrieval?mode=semantic` 결과를 `[IRIS_KNOWLEDGE_CONTEXT]` 로 주입 |

---

## 10. V2.5 완료 기준 (Exit Criteria)

V2.5 마일스톤은 다음을 **모두** 충족할 때 완료로 선언한다.

| # | 지표 | 임계치 |
|---|---|---|
| (a) | L6-D1 의 K5 정상 호출 비율 (30일 누적) | **≥ 95%** (fallback < 5%) |
| (b) | Trigger A 또는 C 로 식별된 Gold 후보 | **≥ 3건** |
| (c) | `X-IRIS-Caller` 헤더 누락률 (`FAULT:anonymous` 비율) | **< 1%** |
| (d) | K5 단일 엔드포인트 가용성 (Telemetry 기록 누락 없음) | **≥ 99%** |

> Trigger B 는 V2.6 K1a 가동 의존이므로 완료 기준에서 제외. (0건이 정상)

---

## 11. V2.6 마일스톤 확장 준비 항목

1. **Gold Lane 공식 승격 + 양식 확정** — V2.5 후보군 기반의 IRIS 압축 표준 양식 정의 및 `lane='gold'` 인덱싱.
2. **Quartz v4 발행 채널 개방** — Gold 전용 정적 그래프 / 시각화 유통.
3. **L5 Observability 대시보드화** — 파일 텔레메트리 → 시각화 + Hit Rate 추적 프레임워크.
4. **K1a 비정형 E2E 가동** — PDF/PPT Drop → K2 클렌징 → K3 분류 → `lane='silver'` 자동 승격. (Trigger B 실효화의 전제)
5. **L1-claw ↔ L2-gateway 통합** — 클라이언트 진입과 프롬프트 주입 게이트웨이의 물리적 통합.

---

## 12. 한 줄 요약

> **IRIS V2.5 (rev3)** 는 사양의 모호성을 *공학적 수치*로 박멸하고, `X-IRIS-Caller` 식별 헤더와 Fallback 10% 알람으로 **K5 결함을 숨김없이 L1(주인)에게 고발하는 자기 의심 메커니즘**을 내장했다. L6 는 더 이상 마일스톤의 목적이 아니라 *데이터 계약을 두드려 보는 검증단*이며, K5 단일 엔드포인트와 Gold 정량 트리거 + Telemetry Zero 의 결합으로 시스템은 비로소 **실험에서 공학으로** 격상되었다.
