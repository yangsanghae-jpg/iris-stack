# IRIS M2 경량 런타임 Phase 1

작성: 2026-08-24

상태: **Phase 1 코드 구축 완료 · M2 Ollama 런타임 검증 대기**

상위 설계: `iris-spc/docs/2026-08-24_IRIS_M5_M2_도우미_런타임_비교설계.md`

## 1. 이번 단계의 실행 경계

M2는 제품별 Compose를 유지하면서 `iris-stack`이 L2 실행 정책과 선택 기동만 조정한다.

```text
선택 제품(SPC / APS / Sales / QMS)
  -> 제품별 독립 Compose와 제품 DB

사용자 호출자
  -> M2 L2 (:8011)
  -> host Ollama (:11434)
  -> qwen3.5:4b 단일 허용 모델
```

M2 기본 Compose에는 다음 서비스를 넣지 않는다.

- OpenWebUI
- OpenClaw
- Firecrawl L4 Search
- Grafana, Prometheus 등 전체 모니터링 오버레이
- 폐기된 L3 `iris-memory`와 memory profile

## 2. 런타임 제한

| 항목 | M2 기본값 | 적용 위치 |
|---|---:|---|
| 허용 모델 | `qwen3.5:4b` | `IRIS_ALLOWED_MODELS` |
| 기본 모델 | `qwen3.5:4b` | `IRIS_DEFAULT_MODEL` |
| 컨텍스트 상한 | 8,192 tokens | Ollama `num_ctx` |
| 출력 상한 | 1,024 tokens | Ollama `num_predict` |
| 웹 검색 | 꺼짐 | `IRIS_SEARCH_ENABLED=false` |
| L3 메모리 | 꺼짐 | `IRIS_MEMORY_ENABLED=false` |

클라이언트가 더 큰 `num_ctx`, `num_predict`, `max_tokens`를 보내도 L2가 M2 상한으로 낮춘다. 허용 목록 밖의 모델은 `/chat`과 `/v1/chat/completions`에서 HTTP 400으로 거부하고 `/models` 및 `/v1/models`에서도 노출하지 않는다.

`GET /health`는 프로세스 생존과 적용 정책을 보여준다. `GET /ready`는 Ollama 연결과 기본 4B 모델 설치까지 확인하며 준비되지 않았으면 HTTP 503을 반환한다.

## 3. 설정과 기동

```bash
cd /Users/iris/Documents/1Dev/iris-stack
cp .env.m2.example .env.m2

# 설정·정책 테스트
./scripts/m2-runtime.sh test

# Ollama 및 4B 모델 확인
./scripts/m2-runtime.sh preflight

# L2만 기동
./scripts/m2-runtime.sh up

# SPC와 QMS를 선택 기동한 뒤 L2 기동
./scripts/m2-runtime.sh up spc qms

# 네 제품을 모두 선택
./scripts/m2-runtime.sh up all
```

제품 인자를 생략하면 `.env.m2`의 `M2_PRODUCTS`를 사용한다. 제품은 각 저장소의 `compose.yml`로 올라가므로 이미지와 DB 소유권이 `iris-stack`으로 합쳐지지 않는다.

## 4. 제품 상태 계약

| 제품 | 기본 상태 URL |
|---|---|
| SPC | `http://127.0.0.1:3340/health` |
| APS | `http://127.0.0.1:7010/api/health` |
| Sales | `http://127.0.0.1:3400/api/v1/health` |
| QMS | `http://127.0.0.1:3350/health` |

URL은 `.env.m2`의 `M2_*_HEALTH_URL`로 바꿀 수 있다. `status`와 `verify-runtime`은 선택된 제품과 L2 `/ready`를 함께 확인한다.

## 5. 현재 남은 범위

이번 단계는 경량 실행 기반만 구축한다. 다음 항목은 아직 구현되지 않았다.

- 사용자 인증·권한·대화 감사 로그를 소유할 제품용 IRIS Gateway
- SPC·APS·Sales·QMS 정형 질문 Direct Handler
- L2와 L4-K 표준 retrieval의 본문 구절·출처 전달 계약
- M2 고정 교차 시스템 workflow
- M5 전달 계약
- 승인형 command

현재 `iris-gateway`는 로컬 개발 작업 통제기이므로 제품용 Gateway 구현으로 간주하지 않는다. L4-K의 현재 표준 retrieval 응답은 문서 메타데이터 중심이어서, L2에 근거 문장을 주입하기 전에 passage와 citation 스키마를 먼저 고정해야 한다.

## 6. Phase 판정

코드와 Compose 기준 Phase 1 범위는 구현됐다. 다만 실제 M2에서 Ollama와 `qwen3.5:4b`가 준비된 상태의 `/ready` 및 질의 응답 검증 전까지 운영 배포 완료로 판정하지 않는다.
