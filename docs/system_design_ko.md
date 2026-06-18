# iris-stack 시스템 설계서

> **계층**: L2 (합성/오케스트레이션) + Observability
> **상태**: L2 게이트웨이 가동, L4-K 미포함
> **작성**: 2026-05-31
> **갱신**: 2026-06-18 — iris-memory(L3) 폐기. memory-admin 컨테이너·`IRIS_MEMORY_*` env·memory-profiles 제거. 아래 본문의 메모리 관련 기술은 *역사 기록*으로만 봐라.

## 1. 한 줄 정의

IRIS 전체(L0–L4-K) 중 **로컬 Docker 합성 계층**으로, OpenWebUI(L1) → L2-Gateway → Ollama(host) + L4-search(Firecrawl) + iris-memory(host:8001) 경로를 한 compose 스택으로 묶어 노출하고, observability 오버레이로 외부 서비스(`iris-system` 포함)까지 관측한다.

## 2. 아키텍처

```
사용자
  ↓ http://localhost:${OPEN_WEBUI_PORT:-3000}
OpenWebUI (L1)
  ↓ OpenAI 호환 API
L2-Gateway (:8010 또는 :8011)
  ├─ Ollama (host:11434)
  ├─ L4-search (l4-search:8020) → Firecrawl SaaS
  └─ iris-memory (host:8001)
                ↑
memory-admin (:18020) — iris-memory DB read-only UI

[Observability overlay]
Prometheus / Grafana / Loki / Promtail / cAdvisor / node-exporter / blackbox-exporter
  ↑ Promtail이 host iris-system/storage 도 read-only 마운트
```

## 3. 핵심 서비스

| Service | Path | Role | Container | Host |
|---|---|---|---|---|
| open-webui | (이미지) `ghcr.io/open-webui/open-webui:main` | L1 채팅 UI | 8080 | `${OPEN_WEBUI_PORT:-3000}` |
| l2-gateway | [l2-gateway/](../l2-gateway/) | OpenAI 호환 라우팅 + 검색 의사결정 + memory bridge | 8010 | `${L2_GATEWAY_PORT}` |
| l4-search | [l4-search/](../l4-search/) | Firecrawl 검색 래퍼 (Node/Express) | 8020 | `${L4_SEARCH_PORT:-8020}` |
| memory-admin | [memory-admin/](../memory-admin/) | iris-memory DB read-only UI (FastAPI+Jinja2) | 8000 | `${MEMORY_ADMIN_PORT:-18020}` |
| Ollama | host process | LLM 런타임 | 11434 | host 직결 |
| iris-memory | host process | L3 영속 메모리 | - | 8001 |

> **불일치**: README는 L2를 `8010`으로 표기하나 `.env`는 `L2_GATEWAY_PORT=8011`. [scripts/status.sh](../scripts/status.sh)는 기본값 8010. 마이그레이션 중인 포트.

## 4. l2-gateway 상세

[l2-gateway/](../l2-gateway/) — **OpenWebUI에 OpenAI 호환 API 노출 → Ollama 위임 + 검색 트리거 판단 시 L4-search 호출 + iris-memory prefetch/writeback**.

(주의: 같은 IRIS 안에 또 다른 게이트웨이 [iris-gateway/](../../iris-gateway/) 가 있음 — 그쪽은 L4-C 컨트롤/도구 게이트웨이. 본 L2는 **LLM 합성 라우팅** 전용.)

### 라우트

| 메서드 | 경로 | 용도 |
|---|---|---|
| GET | `/health` | 헬스 |
| GET | `/v1/models` | OpenAI 호환 모델 리스트 |
| POST | `/v1/chat/completions` | OpenAI 호환 채팅 (스트리밍/비스트리밍) |
| GET | `/search/health` | L4-search 연결성 |
| POST | `/search` | 검색 명시 호출 |
| GET | `/debug/search-decision` | 검색 트리거 디버그 |

### 환경

| 변수 | 의미 |
|---|---|
| `IRIS_SEARCH_ENABLED` | 검색 통합 on/off |
| `IRIS_SEARCH_TRIGGERS` | 한국어 트리거 (기본: `검색,찾아봐,최신,오늘,뉴스,공휴일,주가,가격,2026,법정,일정,트렌드`) |
| `IRIS_MEMORY_*` | 메모리 연동 옵션 |
| `L4_SEARCH_URL` | 기본 `http://l4-search:8020/search` |

### memory-profiles

L2가 시스템 프롬프트로 주입하는 **페르소나/규약 마크다운 뱅크**:

| 파일 | 역할 ([main.py:41-50](../l2-gateway/app/main.py#L41-L50) `MEMORY_FILE_ROLES`) |
|---|---|
| `IDENTITY.md` | 정체성 |
| `USER.md` | 사용자 이해 |
| `SOUL.md` | 성향 |
| `AGENTS.md` | 행동 규칙 |
| `TOOLS.md` | 도구 규칙 |
| `HEARTBEAT.md` | 상태 점검 |
| `BOOTSTRAP.md` | 시작 컨텍스트 |

위치: [memory-profiles/default/](../memory-profiles/default/) — compose에서 L2에 `:ro` 마운트.

## 5. l4-search

[l4-search/server.js](../l4-search/server.js) — Node + Express, 83줄.

- Firecrawl SaaS를 `@mendable/firecrawl-js`로 호출
- `POST /search { query, limit }` → `{ ok, query, count, results: [{title, url, snippet}, ...] }`
- L2만 호출 (OpenWebUI는 직접 안 부름)

## 6. memory-admin

[memory-admin/app/main.py](../memory-admin/app/main.py) — 306 LOC.

- iris-memory(`host:8001`) **read-only 관리 UI**
- host volume: `/Users/iris/Documents/0Dev/iris-memory/data:/app/data:ro` — `memory.db`(SQLite) 직접 조회
- L2 prefetch 미리보기 엔드포인트 (`PrefetchPreviewRequest`)
- FastAPI + Jinja2 템플릿 ([memory-admin/app/templates/](../memory-admin/app/templates/))

## 7. docker-compose 토폴로지

| 파일 | 용도 |
|---|---|
| [docker-compose.yml](../docker-compose.yml) | 기본 4서비스 (open-webui, l2-gateway, l4-search, memory-admin) + external `iris-net` |
| [docker-compose.observability.yml](../docker-compose.observability.yml) | Prometheus / cAdvisor / node-exporter / blackbox / Loki / Promtail / Grafana 7컨테이너 오버레이 |
| [docker-compose.observability.mac.yml](../docker-compose.observability.mac.yml) | macOS Docker Desktop 전용 cAdvisor 볼륨 축소 (`/`, overlayfs rslave 실패 회피, `/var/run / /sys / docker.sock`만 마운트) |

> 외부 네트워크 `iris-net` 사전 생성 필요: `docker network create iris-net` (README/스크립트에 명시 없음 — 운영 노트로 보강 필요).

## 8. Observability 스택

| 컴포넌트 | 버전 | 역할 |
|---|---|---|
| Prometheus | 2.55.1 | 메트릭 수집 |
| cAdvisor | 0.49.1 | 컨테이너 메트릭 |
| node-exporter | 1.8.2 | 호스트 메트릭 |
| blackbox-exporter | 0.25.0 | 외부/내부 HTTP probe |
| Loki | 3.2.1 | 로그 저장 |
| Promtail | 3.2.1 | 로그 수집기 |
| Grafana | 11.3.1 | 대시보드 |

### Prometheus jobs ([observability/prometheus/prometheus.yml](../observability/prometheus/prometheus.yml))

- `prometheus` / `cadvisor` / `node-exporter`
- `iris-services-blackbox` — open-webui, l2-gateway, iris-memory, memory-admin, l4-search, iris-claw, diagnosis 를 `card/surface/role/check` 라벨 체계로 probe

### Grafana 대시보드

- `iris-infra.json`
- `iris-product-readiness.json`
- `iris-services-status.json`
- `iris-v25-k5.json`

### Loki/Promtail

Promtail이 호스트 `/Users/iris/Documents/0Dev/iris-system/storage` 를 `:ro` 마운트 — **iris-system K5 telemetry 로그를 외부에서 수집** ([docker-compose.observability.yml:102](../docker-compose.observability.yml#L102)).

### 알림 룰

[observability/prometheus/rules/iris-product-readiness.yml](../observability/prometheus/rules/iris-product-readiness.yml)

## 9. scripts/

| 스크립트 | 용도 |
|---|---|
| [scripts/status.sh](../scripts/status.sh) | `docker compose ps` + L2/L4 `/health` + `/v1/models` + `docker system df` + 포트 3000/8010/11434/18020 lsof + Ollama `/api/tags` |
| [scripts/config-check.sh](../scripts/config-check.sh) | `docker compose config` + `.env` 덤프 |

## 10. 외부 의존

| 의존 | 위치 | 비고 |
|---|---|---|
| **Host Ollama** | `host.docker.internal:11434` | 컨테이너 안에서 안 띄움 |
| **Host iris-memory** | `host.docker.internal:8001` | L3 |
| **Host iris-system storage** | `/Users/iris/Documents/0Dev/iris-system/storage` | Promtail 로그 수집 |
| **Firecrawl SaaS** | API key 필수 (`FIRECRAWL_API_KEY`) | L4-search 의존 |
| **iris-net** | external Docker network | 다른 iris-* 스택과 공유 |

## 11. 데이터 흐름 (요약)

```
사용자 → OpenWebUI → POST /v1/chat/completions
   ↓ L2-Gateway
   ├─ memory_profiles 시스템 프롬프트 주입
   ├─ memory.prefetch (iris-memory:8001)
   ├─ search_decision → (트리거 hit) → l4-search:8020 → Firecrawl → snippets
   ├─ Ollama:11434 호출 (snippets + prefetch + 사용자 message)
   └─ memory.writeback (옵션)
   ↓ 응답 (streaming / json)
OpenWebUI 렌더
```

## 12. 디렉터리 구조

```
iris-stack/
├── docker-compose.yml
├── docker-compose.observability.yml
├── docker-compose.observability.mac.yml
├── l2-gateway/
│   ├── app/main.py (1655 LOC)
│   ├── Dockerfile, requirements.txt
│   └── app/main.py.bak.step4   (step5 진행 중 백업)
├── l4-search/
│   ├── server.js, package.json, Dockerfile
├── memory-admin/
│   ├── app/main.py, app/templates/, Dockerfile
├── memory-profiles/
│   └── default/{IDENTITY,USER,SOUL,AGENTS,TOOLS,HEARTBEAT,BOOTSTRAP}.md
├── observability/
│   ├── prometheus/{prometheus.yml,rules/}
│   ├── grafana/{provisioning,dashboards}
│   ├── loki/, promtail/
│   ├── blackbox/, cadvisor_on_macos.md
├── scripts/{status.sh, config-check.sh}
├── backup/
└── README.md
```

## 13. 현재 상태

| 영역 | 상태 |
|---|---|
| L2 게이트웨이 ↔ iris-memory 통합 | 완료 |
| L2 ↔ L4-search ↔ Firecrawl | 완료 |
| L4-K knowledge 통합 | **미포함** (iris-system 별도) |
| 포트 정합 (8010 vs 8011) | **불일치 — 정리 필요** |
| README 헤더 ("Step 1: Docker baseline only") | 구식, 본문은 갱신됨 — 헤더 정합성 정리 필요 |
| 백업 잔존 | `l2-gateway/app/main.py.bak.step4`, `backup/` 디렉터리 |
| 호스트 경로 주석 | `docker-compose.observability.yml` 헤더에 `cd /Volumes/0Dev/iris-stack` (실제 `/Users/iris/Documents/0Dev/iris-stack`) — 이전 이력 |

최근 커밋 흐름: `feat: add memory admin read-only UI` → `feat(l2): connect iris memory prefetch and writeback` → `docs: capture L2 L4 search baseline` (활동 중심 = L2 + 메모리).

## 14. 재개발/유지보수 참고

- **iris-net 사전 생성**: `docker network create iris-net` (compose `external: true` 라 자동 생성 안 됨)
- **포트 8010 vs 8011 정리**: `.env`와 README, scripts 기본값 일관성 맞추기
- **observability 시작**: `docker compose -f docker-compose.yml -f docker-compose.observability.yml -f docker-compose.observability.mac.yml up -d` (mac)
- **새 서비스 probe 추가**: `prometheus.yml`의 `iris-services-blackbox` job에 target 추가 + `card/surface/role/check` 라벨
- **L4-K (iris-system) 통합**: V2.6 이월 항목 — 본 스택에 service 추가 가능성

## 참고

- 상위 IRIS 계층: [/Users/iris/Documents/0Dev/ARCHITECTURE.md](../../ARCHITECTURE.md)
- IRIS V2.5 사양: [/Users/iris/Documents/0Dev/docs/system/IRIS_V2.5_계층구조_2026-05-22.md](../../docs/system/IRIS_V2.5_계층구조_2026-05-22.md)
- L1 OpenClaw: [iris-claw/](../../iris-claw/)
- L3 메모리: [iris-memory/](../../iris-memory/)
- L4-K 지식: [iris-system/](../../iris-system/)
- L4-C 게이트웨이 (별개): [iris-gateway/](../../iris-gateway/)
