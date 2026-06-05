---
name: cadvisor-on-macos
description: cAdvisor on macOS Docker Desktop — omit /var/lib/docker mount; use compose labels in PromQL, not name=
metadata:
  type: feedback
---

macOS Docker Desktop 환경에서 cAdvisor(`gcr.io/cadvisor/cadvisor`)는 Linux 호스트와 동작이 다르다.

## 증상 A — PromQL `name=~"iris-.*"` 빈 벡터

- `container_cpu_usage_seconds_total{name=~"iris-.*"}` 결과 **빈 벡터**
- `container_memory_rss{name=...}` 마찬가지
- `up{job="cadvisor"}` 는 정상 1 (cAdvisor 자체는 살아 있음)

**원인:** cAdvisor가 `name=` / `container_label_*` 를 기대 위치에서 못 읽음.

**해결:** compose 라벨 화이트리스트 + PromQL을 compose 라벨로 작성.

```yaml
command:
  - '--docker_only=true'
  - '--store_container_labels=false'
  - '--whitelisted_container_labels=com.docker.compose.project,com.docker.compose.service'
  - '--housekeeping_interval=15s'
```

```promql
sum by (container_label_com_docker_compose_service) (
  rate(container_cpu_usage_seconds_total{
    container_label_com_docker_compose_project=~"iris-stack|iris-memory"
  }[2m])
) * 100
```

## 증상 B — 패널이 계속 비어 있음 (라벨 수정 후에도)

cAdvisor 로그에 반복:

```text
Failed to create existing container: /docker/<id>: failed to identify the read-write layer ID ...
open /rootfs/var/lib/docker/image/overlayfs/layerdb/mounts/<id>/mount-id: no such file or directory
```

**원인:** `docker-compose.observability.yml` 에서 호스트 `/var/lib/docker` 를 마운트하면, macOS 호스트에는 해당 경로가 없고 Docker Desktop VM 내부 경로와 불일치한다.

**해결 (1단계):** `/var/lib/docker/:/var/lib/docker:ro` 볼륨 **제거**.

**해결 (2단계, 여전히 overlayfs mount-id 오류 시):** `/:/rootfs:ro` 마운트도 **제거**. `docker.sock` + `/sys` + `/var/run` 만 유지.

Docker Desktop `overlayfs` 스토리지는 `image/overlayfs/layerdb/mounts/` 트리가 없어 cAdvisor가 레이어 ID를 못 읽는 경우가 많다. 그때는 Mac 호스트에서 **컨테이너 CPU/RSS 패널은 비는 것이 정상**이며, node-exporter·blackbox·Loki로 인프라 관측을 보완한다.

```bash
cd /Users/iris/Documents/0Dev/iris-stack
docker compose -f docker-compose.yml -f docker-compose.observability.yml -f docker-compose.observability.mac.yml up -d cadvisor
```

1~2분 후 `http://<host>:3030/d/iris-infra` 에서 컨테이너 CPU/RSS 패널 확인.

## 적용 규칙

- macOS에서 cAdvisor 쓸 때: 위 command 플래그 + **no** `/var/lib/docker` mount
- 새 IRIS 대시보드 PromQL: `container_label_com_docker_compose_service` 기준
- 관련: VM 역할 분리 — 호스트=Mac 이므로 Linux용 가이드를 그대로 쓰면 빈 화면이 길어짐

**기록:** 2026-05-22 IRIS Observability V2.6 1차 검증
