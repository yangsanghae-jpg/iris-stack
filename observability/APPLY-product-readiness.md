# IRIS — 제품 동작 상태판 적용 가이드 (호스트 M5)

> **무엇이 바뀌었나**: 인프라 메트릭 중심 → **제품(카드) 단위 readiness** 중심.
> 카드 7개: Open WebUI, L2-gateway, iris-memory, memory-admin, L4-search, iris-claw, diagnosis-tool.
> 각 카드는 ✅ 동작 / ⚠️ 부분 / ❌ 불가 종합 상태 + 본체·의존 구성요소 UP/DOWN 표시.

---

## 변경된 파일 (이미 호스트 디스크에 반영됨, SMB)

| 파일 | 변경 |
|---|---|
| `observability/prometheus/prometheus.yml` | blackbox 9 → 16 타깃, card/surface/role/check 라벨 도입 |
| `observability/prometheus/rules/iris-product-readiness.yml` | **신규** — 카드 종합 readiness recording rules |
| `docker-compose.observability.yml` | prometheus rules 디렉토리 마운트 1줄 추가 |
| `observability/grafana/dashboards/iris-product-readiness.json` | **신규** 메인 대시보드 |
| `observability/grafana/dashboards/iris-services-status.json` | "Raw Probe (디버그용)"으로 격하 |
| `observability/grafana/dashboards/iris-infra.json` | secondary 태그 |

---

## STEP 1 — Prometheus 설정·룰 검증 (선택)

```bash
cd /Users/iris/Documents/0Dev/iris-stack

# config 문법
docker run --rm -v "$PWD/observability/prometheus:/cfg" \
  prom/prometheus:v2.55.1 \
  promtool check config /cfg/prometheus.yml

# rule 문법
docker run --rm -v "$PWD/observability/prometheus/rules:/rules" \
  prom/prometheus:v2.55.1 \
  promtool check rules /rules/iris-product-readiness.yml
```

둘 다 `SUCCESS` 나와야 합니다.

## STEP 2 — Prometheus 재기동 (rules 디렉토리 마운트가 새로 생겼으므로 reload만으로는 부족)

```bash
cd /Users/iris/Documents/0Dev/iris-stack

docker compose \
  -f docker-compose.yml \
  -f docker-compose.observability.yml \
  up -d prometheus
```

`-d`로 띄우면 변경 감지 후 재생성됩니다. 컨테이너 그대로면 강제로:

```bash
docker compose -f docker-compose.observability.yml restart prometheus
```

## STEP 3 — Grafana 재기동 (provisioning 폴더가 dashboards 새 파일을 인식)

```bash
docker compose -f docker-compose.observability.yml restart grafana
```

Grafana는 보통 자동 재스캔하지만 새 대시보드가 안 보이면 위 명령으로 강제.

## STEP 4 — 검증

```bash
# Prometheus 타깃 (9099 포트 표시 안 되면 카드 라벨 누락)
curl -s 'http://localhost:9090/api/v1/query?query=probe_success{job="iris-services-blackbox"}' \
  | jq '.data.result | group_by(.metric.card) | map({card: .[0].metric.card, total: length, up: (map(.value[1] | tonumber) | add)})'

# Recording rule 확인
curl -s 'http://localhost:9090/api/v1/query?query=iris:card_ready_v2' \
  | jq '.data.result[] | {card: .metric.card, ready: .value[1]}'
```

기대값 예시:
```
{"card": "open-webui",  "ready": "1"}    # ✅
{"card": "iris-claw",   "ready": "1"}    # ✅
{"card": "diagnosis",   "ready": "0"}    # ❌ (8000 Exited)
```

## STEP 5 — 브라우저 확인

**호스트 M5 (localhost) — 제품 동작 상태판 직링크:**

http://localhost:3030/d/iris-product-readiness/24a3c62?orgId=1&from=now-1h&to=now&timezone=browser&refresh=30s

또는 `http://localhost:3030` → IRIS 폴더 → **IRIS — 제품 동작 상태판**

> VM에서 볼 때만 `10.211.55.2`로 호스트 IP를 바꿉니다.

각 카드 헤더가 ✅/⚠️/❌ 색깔로 표시되고, 옆 테이블에 본체·의존이 UP/DOWN으로 나오면 정상.

기존 두 대시보드는:
- **IRIS V2.5 — K5 Telemetry & 4 KPIs** (그대로, K5 로그 생기면 채워짐)
- **IRIS — 인프라 & 헬스체크** (보조용)
- **IRIS — Raw Probe (디버그용)** (이전 services-status, 격하됨)

---

## 트러블슈팅

### `iris:card_ready_v2`가 카드 일부에 대해 결과 없음
- 본체(role=body) probe가 아예 안 잡혀 있을 가능성. `probe_success{role="body"}` 로 확인.
- 또는 라벨 누락 — `prometheus.yml`의 `static_configs` 라벨 잘못 됐는지.

### 카드는 ✅인데 실제로 안 동작
- v1은 /health 200만 봅니다. 깊은 기능 검증은 다음 단계 (사용자가 v1 확정).
- 예: L4-search는 `/health` 200이어도 Firecrawl 키 없으면 실제 검색은 실패.

### diagnosis 카드가 항상 ❌
- 정상. diagnosis-api(8000)이 Exited 상태이거나 llm-gateway(8010)가 안 떠 있으면 ❌.
- 진단툴 자체를 다시 띄워야 ✅로 전환.
