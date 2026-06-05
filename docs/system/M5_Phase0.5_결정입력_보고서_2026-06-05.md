# M5 Phase 0.5 결정 입력 보고서

- **실행 일시:** 2026-06-05 (M5 `irisM5.local`)
- **목적:** 결정 대기 3가지에 대한 M5 실측 근거 + iris-system 네이티브 기동 검증
- **선행:** [M5_DB분리_및_추가진단_보고서_2026-06-05.md](./M5_DB분리_및_추가진단_보고서_2026-06-05.md)

---

## Executive Summary

| 결정 항목 | M5 실측 결론 | 권고 |
|-----------|--------------|------|
| **1. iris-system 실행 모델** | 네이티브 **즉시 불가** (venv 깨짐, Python 3.9) | **A. Docker compose 추가** |
| **2. 통제 UI** | Grafana `iris-v25-k5` KPI 4종 이미 존재 | **동의** — 관측=Grafana, 운영=Streamlit |
| **3. storage 분리** | Promtail이 `iris-system/storage` 경로 고정 | **Phase 0.5에서 즉시** (K5 telemetry 전) |

---

## Part 1. iris-system 네이티브 기동 검증 (옵션 B)

### 1.1 `.venv` 상태

```text
.venv/bin/python  → python3.14 (symlink)
.venv/bin/uvicorn → 존재 (2026-04-13)
```

```bash
.venv/bin/pip check
# bad interpreter: .../python3.14: no such file or directory
```

**판정:** `.venv`는 **다른 머신(M2)에서 만든 Python 3.14 venv가 iCloud로 동기화**되어 M5에서 깨진 상태. iCloud 동기화 제외 대상(§11.2)과 일치.

### 1.2 M5 시스템 Python

```text
/usr/bin/python3 → Python 3.9.6
fastapi / uvicorn → 미설치
```

코드는 **PEP 604** (`list[str] | None`, `IngestRequest | None`) 사용 — **런타임 최소 Python 3.10+** 필요. 3.9로는 import 단계에서 실패.

**해당 파일 예:**

- `apps/wiki/server.py` — `files: list[str] | None`
- `apps/router/server.py` — `files: list[str] | None`
- `apps/ingest/reference_diagnosis.py` — `list[str] | None`, `dict[str, int]`

### 1.3 네이티브 uvicorn 5초 기동 시도

| 대상 | 결과 |
|------|------|
| `.venv/bin/python -m uvicorn` (router/wiki) | **실행 불가** — interpreter 없음 |
| `/usr/bin/python3 -m uvicorn` | **실행 불가** — fastapi 미설치 |
| `timeout 5` 명령 | macOS에 `timeout` 없음 (exit 127) — Docker 검증에서 `timeout` 사용 |

### 1.4 Docker 컨테이너 내 검증 (옵션 A 타당성)

로컬 이미지 `python:3.11-slim`으로 마운트 실행:

```bash
docker run --rm -v .../iris-system:/app -w /app python:3.11-slim bash -c '
  pip install fastapi uvicorn requests python-multipart
  python -c "from apps.router.server import app"  # OK
  python -c "from apps.wiki.server import app"    # OK
  timeout 5 python -m uvicorn apps.router.server:app --port 18080  # Started OK
  timeout 5 python -m uvicorn apps.wiki.server:app --port 18081    # Started OK
'
```

| 검사 | 결과 |
|------|------|
| `pip check` | No broken requirements found |
| router import | OK — `IRIS 라우터` |
| wiki import | OK — `IRIS 위키 엔진` |
| router uvicorn | `Uvicorn running on http://127.0.0.1:18080` |
| wiki uvicorn | `Uvicorn running on http://127.0.0.1:18081` |

**판정:** 앱 코드 자체는 건강. **M5에서 즉시 옵션 B 불가**, Dockerfile + compose가 최단 경로.

### 1.5 옵션 A vs B 최종 비교 (M5 실측 반영)

| | A. Docker compose | B. 네이티브 + launchd |
|--|-------------------|----------------------|
| **M5 지금** | `python:3.11-slim`으로 기동 확인됨 | venv 깨짐, Python 3.9, 재구축 필요 |
| iris-stack 통일 | L2/memory/claw와 동일 패턴 | 유일한 네이티브 예외 |
| env/포트 | compose 표준화 | plist + venv 수동 |
| hot-reload | volume mount로 가능 | 가능하나 venv 먼저 복구 |
| **권고** | ✅ **채택** | ❌ M5 단독 운영에는 부적합 |

### 1.6 옵션 A 구현 스케치 (다음 작업)

```yaml
# iris-stack/docker-compose.yml 추가 예시 (초안)
iris-k5-router:
  build: ../iris-system  # Dockerfile 필요
  ports: ["18080:18080"]
  volumes:
    - ../iris-system/knowledge:/app/knowledge
    - ~/iris-local/storage:/app/storage   # Phase 0.5 후
  networks: [iris-net]

iris-k5-wiki:
  build: ../iris-system
  command: uvicorn apps.wiki.server:app --host 0.0.0.0 --port 18081
  ports: ["18081:18081"]
  volumes: (동일)
```

- 베이스: `python:3.11-slim`
- requirements: `apps/router/requirements.txt` + `apps/wiki/requirements.txt` 합침
- Promtail 마운트: **호스트 경로 symlink 유지** 시 `iris-system/storage` 변경 불필요

---

## Part 2. 통제 UI — Grafana + Streamlit 분리

### 2.1 제안 (마스터안)

| 영역 | 도구 | Phase |
|------|------|-------|
| 관측 (KPI, fallback율, 분포) | Grafana `iris-v25-k5` | 이미 프로비저닝됨 |
| 운영 (Ask, Inbox, Browse, Curate) | Streamlit `iris-console` | Phase 6/7 |

### 2.2 M5 근거

- Grafana `:3030` — 대시보드 4개, datasource Prometheus + Loki
- `iris-v25-k5.json` — K5 정상호출 ≥95%, Caller 누락률, Fallback 알람 패널 **이미 정의**
- Loki 스트림 0건 = K5 미기동 때문이지 Grafana 부재가 아님

### 2.3 판정

**동의.** 이전 L1-console(Streamlit) 논의와 충돌 없음.

- **§11 통제 화면 (관측)** → Grafana 정본
- **§11 운영 콘솔 (액션)** → Streamlit Phase 6/7
- Streamlit으로 KPI 차트를 다시 그리는 작업은 **불필요** (중복 제거)

V2.5.1 반영 문구 예:

> §11.6 관측 UI는 Grafana(`iris-v25-k5`)를 정본으로 한다. Streamlit 콘솔은 Ask/Inbox/Curate 운영 UI에만 한정한다.

---

## Part 3. storage 분리 — Phase 0.5

### 3.1 왜 지금인가

- Promtail: `/Users/iris/Documents/0Dev/iris-system/storage/iris_k5_telemetry*.log`
- K5 router 기동 시 telemetry가 `storage/`에 쓰이기 시작
- `storage/`가 iCloud 안에 있으면 `_index.db`와 동일한 WAL/동시쓰기 클래스 리스크

### 3.2 권고 절차 (Phase 0.5)

```bash
mkdir -p ~/iris-local/storage
mv ~/Documents/0Dev/iris-system/storage/* ~/iris-local/storage/ 2>/dev/null || true
rmdir ~/Documents/0Dev/iris-system/storage 2>/dev/null || true
ln -sf ~/iris-local/storage ~/Documents/0Dev/iris-system/storage
```

- Promtail compose 마운트 경로 `.../iris-system/storage` → **symlink 따라감, compose 수정 불필요**
- `~/iris-local/`은 iCloud 밖 (백업 `_index.db`와 동일 존)

### 3.3 현재 storage 내용

```text
storage/
├── _index.db (0 bytes placeholder)
└── sqlite/
```

데이터 거의 없음 → **지금 이동 비용 최소**. Phase 0.5 진입 직전 실행 권장.

### 3.4 판정

**Phase 0.5에 묶기 — 동의.** K5 Docker 기동(옵션 A) **직전**에 실행.

---

## Part 4. 권장 Phase 0.5 순서 (M5)

| 순서 | 작업 | 머신 | 상태 |
|------|------|------|------|
| 0 | `_index.db` → `.nosync` | M5 | ✅ 완료 |
| 1 | `storage/` → `~/iris-local/storage` + symlink | M5 | ⏳ 다음 |
| 2 | iris-system Dockerfile 작성 | M2 편집 → M5 빌드 | ⏳ |
| 3 | `docker-compose.yml`에 router+wiki 추가 | M2 편집 → M5 up | ⏳ |
| 4 | router `:18080` health + telemetry 로그 생성 확인 | M5 | ⏳ |
| 5 | Grafana `iris-v25-k5` 패널 데이터 확인 | M5 | ⏳ |

---

## Part 5. V2.5.1 문서 반영 체크리스트

- [ ] §11.1 머신 역할 (M2/M5)
- [ ] §11.2 iCloud 제외 목록 (`_index.db*` ✅, `storage/` Phase 0.5)
- [ ] §11.6 관측=Grafana / 운영=Streamlit 분리
- [ ] §7 Phase 표 — **머신 컬럼** + iris-system **Docker(A)** 명시
- [ ] L5 "V2.6 대시보드화" → **이미 구현됨** 으로 상태 갱신
- [ ] `.venv` iCloud 동기화 **금지** 명시 (이번 venv 깨짐이 실증)

---

## 부록: 실행 로그 원문

### 네이티브 venv

```text
$ ls .venv/bin/uvicorn
  존재 (python3.14 symlink 대상 없음)

$ .venv/bin/pip check
  bad interpreter: .../python3.14: no such file or directory

$ /usr/bin/python3 --version
  Python 3.9.6

$ python3 -c "import fastapi"
  ModuleNotFoundError: No module named 'fastapi'
```

### Docker python:3.11-slim

```text
pip check → No broken requirements found
router import → OK IRIS 라우터
wiki import   → OK IRIS 위키 엔진
uvicorn router:18080 → Application startup complete
uvicorn wiki:18081   → Application startup complete
```

---

*생성: M5 Phase 0.5 결정 입력 검증 · 2026-06-05*
