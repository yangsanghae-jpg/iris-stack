# M5 Phase 0.5 — K5 Docker 기동 보고서

- **실행 일시:** 2026-06-05 13:32 (M5 `irisM5.local`)
- **목표:** `iris-k5-wiki` + `iris-k5-router` 빌드·기동·검증 (Phase 0.5 종료)
- **선행:** M2 `iris-k5-system:local` Dockerfile/compose 검증 통과, iCloud로 `iris-system/` 동기화

---

## Executive Summary

| 단계 | 결과 |
|------|------|
| Dockerfile 도착 (iCloud) | ✅ |
| `docker compose build iris-k5-wiki` | ✅ `iris-k5-system:local` (843MB) |
| `docker compose up -d` wiki + router | ✅ 둘 다 **healthy** |
| wiki `/health` | ✅ `{"ok":true,"service":"iris-wiki-engine"}` |
| router `/health` | ✅ `{"ok":true,"service":"iris-router"}` |
| `_index.db` symlink (컨테이너 내) | ✅ dead link **아님**, documents **630** |
| `storage/` 마운트 | ✅ `~/iris-local/storage` → `/app/storage` |
| K5 telemetry / Grafana 패널 | ⏸️ Phase 5.5 — **아직 빈 패널** (정상) |

**Phase 0.5 판정: ✅ 종료.** Phase 1 (Schema) 진입 가능.

---

## 이전 중단 원인

| 시도 | 원인 |
|------|------|
| 1차 빌드 (12:06) | Docker 빌드 중 `apt-get` — `deb.debian.org` DNS/연결 실패 (exit 100) |
| 2차 빌드 (13:06) | apt 다운로드 **~24 kB/s** — 7분+ 소요, 세션 **타임아웃으로 중단** |
| 3차 빌드 (13:31) | apt 레이어 캐시 + 네트워크 정상 → **~83초 만에 완료** |

**교훈:** M5에서 최초 `iris-k5-system` 빌드는 **10~15분** 잡고 백그라운드로 돌려야 함. 재시도 시 apt 레이어 캐시로 단축됨.

`git pull` iris-stack: **실패** (`Host key verification failed`) — compose 변경은 이미 M5 로컬/iCloud에 반영되어 있어 기동에는 영향 없음.

---

## 1. 빌드

```bash
cd ~/Documents/0Dev/iris-stack
docker compose build iris-k5-wiki
```

```text
IMAGE: iris-k5-system:local
ID:    a0f2f6f9fbb7
SIZE:  843MB (content 189MB)
BASE:  python:3.11-slim
```

`iris-k5-router`는 동일 이미지, `command`만 오버라이드.

---

## 2. 기동

```bash
docker compose up -d iris-k5-wiki iris-k5-router
```

| 컨테이너 | 상태 | 포트 |
|----------|------|------|
| `iris-k5-wiki` | Up **healthy** | `18081` |
| `iris-k5-router` | Up **healthy** | `18080` |

---

## 3. 헬스체크

```bash
curl http://127.0.0.1:18081/health
# {"ok":true,"service":"iris-wiki-engine"}

curl http://127.0.0.1:18080/health
# {"ok":true,"service":"iris-router"}
```

---

## 4. 동작 확인

### wiki history

```bash
curl "http://127.0.0.1:18081/wiki/history?limit=5"
```

```json
{"status":"ok","count":4,"items":[...]}
```

`wiki_history.db`가 `/app/storage/sqlite/`에서 정상 읽힘.

### router → wiki 라우팅

```bash
curl -X POST http://127.0.0.1:18080/route \
  -H "Content-Type: application/json" \
  -d '{"user_text":"위키에서 MES 설명 찾아봐"}'
```

→ `route: knowledge_query`, `source: wiki`, `ok: true` (wiki 엔진 응답 확인)

`WIKI_BASE_URL=http://iris-k5-wiki:18081` — compose 서비스명 해석 **정상**.

---

## 5. 잠재 이슈 검증 — `_index.db` symlink

```bash
docker exec iris-k5-wiki ls -la /app/knowledge/_index.db
# lrwxr-xr-x → .nosync/_index.db  ✅ (dead link 아님)

docker exec iris-k5-wiki ls -la /app/knowledge/.nosync/_index.db
# -rw------- 1921024 bytes  ✅

docker exec iris-k5-wiki python3 -c \
  "import sqlite3; print(sqlite3.connect('/app/knowledge/_index.db').execute('SELECT COUNT(*) FROM documents').fetchone()[0])"
# 630  ✅
```

**결론:** `knowledge/` 전체 마운트 방식 유효. compose volume을 `.nosync` 직접 마운트로 바꿀 필요 **없음**.

---

## 6. storage 마운트

```bash
docker exec iris-k5-wiki ls -la /app/storage/
```

```text
/app/storage/          ← 호스트 ~/iris-local/storage
├── _index.db (0B placeholder)
└── sqlite/wiki_history.db
```

Promtail `/mnt/iris-system-storage` — `iris-system/storage` symlink 경유 **정상**.

---

## 7. Grafana / telemetry (Phase 5.5 이후)

| 항목 | 현재 |
|------|------|
| `iris_k5_telemetry*.log` | **없음** (telemetry append 미구현) |
| Loki labels | 비어 있음 |
| Grafana `iris-v25-k5` | **빈 패널** — Phase 0.5 범위 밖, 정상 |

패널 점등은 **Phase 5.5** (telemetry 코드) 이후.

확인 URL: http://127.0.0.1:3030/d/iris-v25-k5

---

## 8. 포트 충돌

| 포트 | 점유 | 상태 |
|------|------|------|
| 18080 | `iris-k5-router` | ✅ |
| 18081 | `iris-k5-wiki` | ✅ |
| 8081 | `iris-cadvisor` (다른 서비스) | 충돌 없음 |

네이티브 uvicorn 미기동 — 진단 보고서와 일치.

---

## Phase 0.5 완료 체크리스트

- [x] `_index.db` → `.nosync` (iCloud 밖)
- [x] `storage/` → `~/iris-local/storage`
- [x] launchd 일일 백업 plist
- [x] 깨진 `.venv` 제거
- [x] `iris-k5-system:local` M5 빌드
- [x] `iris-k5-wiki` + `iris-k5-router` healthy
- [x] symlink + DB 630 검증
- [ ] K5 telemetry → Loki (Phase 5.5)
- [ ] Grafana 패널 점등 (Phase 5)

---

## 다음: Phase 1 (Schema)

M5에서 K5가 살아있으므로 M2에서 Schema 마이그레이션 작성 후 **M5에서 실행·검증** 패턴으로 진행.

---

*생성: M5 K5 Docker 기동 검증 · 2026-06-05*
