# IRIS Observability Stack — 호스트 실행 지시서

> **대상:** 호스트 M5 Mac (10.211.55.2). VM에서는 실행 불가.
> **선택지:** Grafana + Prometheus + cAdvisor + Node Exporter + Blackbox + Loki + Promtail (총 7 컨테이너)
> **추정 자원:** RAM ~700MB, 디스크 (Loki 90일 보존 + Prometheus 30일 보존) ~수 GB

---

## STEP 1 — 사전 확인

```bash
cd /Users/iris/Documents/0Dev/iris-stack

# 외부 네트워크가 살아 있는지
docker network ls | grep iris-net

# 기존 iris-stack 5개 컨테이너 살아 있는지 (없으면 먼저 up)
docker compose ps
```

## STEP 2 — Observability 스택 기동

```bash
cd /Users/iris/Documents/0Dev/iris-stack

docker compose \
  -f docker-compose.yml \
  -f docker-compose.observability.yml \
  up -d
```

7개 컨테이너가 새로 뜹니다:
`iris-prometheus`, `iris-cadvisor`, `iris-node-exporter`, `iris-blackbox-exporter`, `iris-loki`, `iris-promtail`, `iris-grafana`

## STEP 3 — 헬스체크 (호스트 측)

```bash
docker compose -f docker-compose.yml -f docker-compose.observability.yml ps

# 각 엔드포인트 확인
curl -s http://localhost:9090/-/ready                         # Prometheus
curl -s http://localhost:3100/ready                           # Loki
curl -s http://localhost:8081/healthz                         # cAdvisor
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3001/   # Grafana → 302
```

## STEP 4 — VM 측 도달성 확인 (VM에서 실행)

```bash
for p in 3030 9090 3100 8081 9100 9115; do
  nc -vz -G 2 10.211.55.2 $p 2>&1 | sed "s/^/[port $p] /"
done
```

**예상:** 6개 모두 `succeeded`.

## STEP 5 — 브라우저 접속

### 호스트 M5 (localhost)

| URL | 용도 |
|---|---|
| `http://localhost:3000` | **Open WebUI** (L1 채팅) |
| `http://localhost:8080` | **Quartz wiki** (`npx quartz build --serve` 실행 시) |
| [제품 동작 상태판](http://localhost:3030/d/iris-product-readiness/24a3c62?orgId=1&from=now-1h&to=now&timezone=browser&refresh=30s) | **IRIS — 제품 동작 상태판** (admin/iris-local) |
| `http://localhost:3030` | Grafana 홈 |
| `http://localhost:9090` | Prometheus 쿼리 콘솔 (디버깅용) |
| `http://localhost:3001` | diagnosis-tool UI (별도 `serve-client.sh`) |
| `http://localhost:8011/health` | L2 Gateway |
| `http://localhost:8001/health` | iris-memory |
| `http://localhost:18789` | iris-claw |

### VM에서 호스트 Grafana (Parallels Shared Network)

| URL | 용도 |
|---|---|
| `http://10.211.55.2:3000` | Open WebUI |
| `http://10.211.55.2:8080` | Quartz wiki |
| `http://10.211.55.2:3030` | Grafana (호스트 IP) |
| `http://10.211.55.2:9090` | Prometheus |

Grafana → Dashboards → IRIS 폴더:
- **IRIS — 제품 동작 상태판** (`iris-product-readiness`)
- **IRIS V2.5 — K5 Telemetry & 4 KPIs**
- **IRIS — 인프라 & 헬스체크**

---

## 주의 사항

1. **Promtail 마운트 경로** — `docker-compose.observability.yml`에서 K5 telemetry 로그 경로를 `/Users/iris/Documents/0Dev/iris-system/storage`로 묶어 두었습니다. 실제 경로가 다르면 그 줄을 수정하세요.

2. **K5 telemetry 로그가 아직 없는 상태** — V2.5 단일 엔드포인트가 가동되어 로그를 쓰기 시작해야 K5 대시보드가 채워집니다. 그 전까지 인프라 대시보드는 정상이지만 K5 패널은 빈 화면.

3. **포트 3030** — 진단툴(`3001`)·OpenWebUI(`3000`)와 충돌 없음. Grafana 컨벤션상 3030을 자주 씀.

4. **Grafana 익명 뷰어 활성화** — 로컬 환경 가정. 외부 노출 시 `.env`에서 `GF_AUTH_ANONYMOUS_ENABLED` 끄세요.

## 정지 / 제거

```bash
# 정지만
docker compose -f docker-compose.observability.yml stop

# 컨테이너 + 네트워크 제거 (볼륨은 유지 — 데이터 보존)
docker compose -f docker-compose.observability.yml down

# 데이터까지 완전 초기화
docker compose -f docker-compose.observability.yml down -v
```
