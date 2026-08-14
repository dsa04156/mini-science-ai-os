# ETRI 내부 제품 릴리스 결과 — 2026-08-11

## 판정

`INTERNAL_PRODUCT=READY`

ETRI 신뢰 내부망에서 사용하는 제품으로 배포와 Release Gate를 완료했다. 외부 인터넷 공개형 제품은 이번 범위가 아니며, TLS/OIDC·원격 DR은 향후 확장 항목이다. Flannel-only CNI의 Pod NetworkPolicy enforcement는 검증되지 않았지만 제품 Ingress에는 Traefik IP Allowlist가 적용됐다.

## 릴리스 식별자

```text
Version: 0.3.1
Profile: internal-production
Access mode: trusted-network
Image: 192.168.0.56:5000/mini-science-ai-os:0.3.1
Digest: sha256:f2a36e42338a9bbfa3fd9d627aa33ace2fcf2f63add7e1c7465b9590acfd61b5
Product URL: http://science-workspace.192.168.0.56.nip.io/portal/
Diagnostic URL: http://192.168.0.56:8090/portal/
Korean guide: http://mini-science-ai-os.192.168.0.56.nip.io/
Korean guide 0.0.0.0 binding: http://192.168.0.56:8088/
```

## 변경한 파일

- `VERSION`, `Makefile`, `clusters/lab/kustomization.yaml`
- `tenants/etri/product.yaml`, API/MCP availability patch
- `services/science_os/job_api.py`, `mcp_server.py`, `portal/*`
- `scripts/product-status.sh`, `release-check.sh`, `test.sh`
- `tests/*`, `documentation/*`, `docs/ADR/0003-*`, 운영 문서
- 모든 운영 Runtime Image를 0.3.1로 고정

## 실행한 핵심 명령

```text
make bootstrap
make release-check
make status
Playwright open/snapshot/fill/click/dialog-accept/screenshot/console
kubectl get pods ... imageID
kubectl get middleware science-workspace-internal-only
curl product /readyz
```

## 실제 검증 결과

```text
Unit/API: 17 passed
Release gate: PASS
Product status: INTERNAL_PRODUCT=READY
Ready response: version=0.3.1, profile=internal-production, accessMode=trusted-network
ETRI API: 2/2 Ready, two Nodes
ETRI MCP: 2/2 Ready, two Nodes
PDB: minAvailable=1
tenant-kist Namespace: NotFound
Ingress root/portal/readiness: 307/200/200
Ingress IP allowlist: 192.168.0.0/24, 10.244.0.0/16, 127.0.0.0/8
0.0.0.0:8090: LISTEN
0.0.0.0:8088: LISTEN, HTML HTTP 200
0.0.0.0:8091: absent
Browser console: 0 errors, 0 warnings
```

네 개 API/MCP Pod 모두 위 0.3.1 Digest를 사용하며 `etri-ser0001-cg0msb`, `etri-ser0002-cgnmsb`에 분산됐다.

## 제품 기능 증거

- MCP Job `21b1a3d27e52`, KFP Run `90c31a70-692b-4e27-ac62-f22a0e812a3b`: 제출·상태 조회·취소 PASS.
- Portal Job `efbb4d3e53ed`, KFP Run `56cca033-5468-4a00-85c8-edc41ba6307e`: 브라우저 제출·상세 조회·취소 PASS. KFP 이력은 `RUNNING → CANCELING → FAILED`로 종료됐으며 이는 사용자 취소의 현재 KFP terminal 표현이다.
- Portal에서 ETRI 5/5 Ready Node, 2 GPU Node, 실제 HAMi Resource `nvidia.com/gpu`, `nvidia.com/gpumem`, `nvidia.com/gpucores` 조회 PASS.
- Desktop: `output/playwright/etri-internal-product-0.3.1-desktop.png`.
- Mobile: `output/playwright/etri-internal-product-0.3.1-mobile.png`.
- Browser title `NAIS Science Workspace`, sidebar `ETRI Internal Workspace · v0.3.1`.
- Release evidence: `docs/evidence/release-check-20260811T060726Z.md`.
- Bootstrap evidence: `docs/evidence/bootstrap-20260811T060008Z.md`.
- Image build evidence: `docs/evidence/build-images-20260811T060030Z.md`.

## 보안 검증

```text
agent-runtime -> ETRI jobs/pods/secrets: no/no/no
science-job-api -> ETRI secrets: no
pipeline-runner-etri -> default jobs create: no
unauthenticated direct API: 401
trusted-network portal session: 200
Origin 없는 Cookie DELETE: 403
API docs: 404
disallowed image: 400
privileged/hostPath: 422/422
```

## 운영상 알려진 한계

- Flannel-only CNI라 Pod NetworkPolicy의 실제 패킷 차단은 검증하지 못했다. Ingress 접근은 Traefik IP Allowlist로 제한한다.
- MySQL/MinIO가 `local-path` PVC라 Node 장애용 원격 복구는 제공하지 않는다. 데이터 보존 등급을 높일 때 외부 DB/Object Storage로 이전한다.
- Argo CD App-of-Apps Manifest는 있으나 게시 Git URL이 없어 현재 배포는 `make bootstrap`으로 관리한다.
- `kubeconform`, `shellcheck` 미설치로 kubectl client validation과 Python/Manifest 보안 테스트를 사용했다.
- HAMi 논리 Quota는 물리 GPU 성능 격리 보장이 아니다.
- Kubeflow 2.17.0 원격 GitHub Kustomize 재조회가 27초 타임아웃됐지만, 기존 고정 버전 Runtime의 모든 Deployment와 실제 KFP Run 연동은 정상 검증됐다.
- 롤링 배포 전 Pod를 가리키던 기존 8090 Port Forward는 빈 응답을 반환해 중지하고 새 API Pod로 재연결했다. 재연결 후 `127.0.0.1:8090`, `192.168.0.56:8090`의 `/readyz`가 모두 0.3.1 Ready를 반환했다.

위 한계는 외부 공개·고가용 DR·GitOps 자동화 범위를 제한하지만, 승인된 ETRI 내부망 제품의 작업 제출/운영 기능을 막지 않는다.

## 운영 판정

ETRI 내부 사용 가능. 사용자는 접근 키 없이 제품 URL에서 Science Job 제출, Queue/Kubeflow 상태 확인, Metric/Artifact 조회, 작업 취소를 수행할 수 있다. Agent는 MCP 6개 Tool로 동일 범위의 자동화를 수행한다.
