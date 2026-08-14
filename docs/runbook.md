# Runbook

## 설치와 갱신

```bash
make inventory
make validate
make bootstrap
```

`bootstrap`은 프로젝트 Namespace에만 적용하며 기존 HAMi, Prometheus, Grafana, Argo CD, KubeEdge, State Aggregator를 변경하지 않는다. KFP는 `2.17.0`, Kueue는 `0.17.3`, Argo Workflows는 KFP 2.17.0에 포함된 `v4.0.5` Manifest를 사용한다. Secret은 먼저 `scripts/ensure-secrets.sh`로 생성해야 한다.

## 상태 확인

```bash
kubectl get deploy,pod,svc,pvc -n kubeflow
kubectl get sts,pod,svc,pvc -n science-ai-mlops
kubectl get deploy,pod,svc -n tenant-etri
kubectl get clusterqueue,resourceflavor
kubectl get localqueue,workload -A
kubectl get jobs -A -l science-ai.io/managed-by=mini-science-ai-os
```

KFP Health와 UI:

```bash
kubectl get --raw '/api/v1/namespaces/kubeflow/services/http:ml-pipeline:8888/proxy/apis/v2beta1/healthz'
kubectl -n kubeflow port-forward --address=0.0.0.0 svc/ml-pipeline-ui 8080:80
```

UI는 `http://<호스트-IP>:8080`이다. 인증/TLS 없는 ClusterIP의 임시 Port Forward이므로 내부망에서만 사용한다.

## 연구자 포털

ETRI 제품 URL은 Traefik Ingress가 제공하므로 운영자 Shell에 종속되지 않는다.

```text
http://science-workspace.192.168.0.56.nip.io/portal/
```

Ingress 장애를 분리 진단할 때만 포털을 `0.0.0.0:8090`에 임시 바인딩한다.

```bash
make portal
```

| Scope | URL | 포털 경계 |
|---|---|---|
| ETRI 제품 URL | `http://science-workspace.192.168.0.56.nip.io/portal/` | `192.168.0.0/24` Allowlist, ETRI 고정 HttpOnly 세션, Rate Limit |
| ETRI 진단 URL | `http://192.168.0.56:8090/portal/` | Port Forward가 실행 중일 때만 사용 |

접근 키 입력은 없다. 포털은 Traefik IP Allowlist를 통과한 내부망 요청에 대해 같은 Origin의 `POST /v1/portal/session`으로 8시간짜리 Tenant 고정 HttpOnly Cookie를 자동 발급하고, 상태 변경 요청은 Same-Origin일 때만 허용한다. 직접 API와 MCP는 계속 `tenant-api-token`을 요구한다. 포털에서 다음을 수행할 수 있다.

- Ready/GPU Node와 실제 HAMi Resource 이름 조회
- Tenant Job 목록, 검색, 상태 필터
- CPU/GPU Science Job 제출
- Kueue Admission/대기 사유와 Kubeflow Run 상태 조회
- Metric, Parameter, Artifact 조회
- 자기 Tenant Job 취소

포털 프로세스 확인:

```bash
kubectl get ingress,pdb -n tenant-etri
curl -I -H 'Host: science-workspace.192.168.0.56.nip.io' http://192.168.0.56/portal/
ss -ltnp | grep -E ':8090\b'
curl -I http://127.0.0.1:8090/portal/
```

Deployment 롤아웃 중 진단용 `kubectl port-forward`가 이전 Pod 연결을 잃으면 `make portal`을 다시 실행한다. 제품 URL은 2개 API Replica와 PDB를 사용한다. 자동 세션 갱신이 실패하면 사이드바의 `세션 새로고침`을 누른다. 외부 운영 전 현재 Ingress에 TLS/OIDC를 추가해야 한다.

## ETRI-only 전환과 Release Gate

```bash
CONFIRM_REMOVE_KIST=tenant-kist make etri-only
make release-check
make status
```

`etri-only`는 Namespace 소유권 Label이 정확히 일치할 때만 `tenant-kist`와 `kubeflow/pipeline-runner-kist*`를 제거한다. 공유 Kubeflow Metadata, MinIO, MySQL은 보존하므로 과거 KIST 실행 이력은 별도 데이터 보존 정책에 따라 정리한다.

## Science Job 제출과 조회

```bash
export SCIENCE_TOKEN="$(kubectl get secret tenant-api-token -n tenant-etri -o jsonpath='{.data.token}' | base64 -d)"
kubectl -n tenant-etri port-forward svc/science-job-api 18080:8000
curl -sS -X POST http://127.0.0.1:18080/v1/jobs \
  -H "X-Science-Token: ${SCIENCE_TOKEN}" \
  -H 'Content-Type: application/json' \
  --data @workloads/kubeflow-demo/request.json
curl -sS -H "X-Science-Token: ${SCIENCE_TOKEN}" http://127.0.0.1:18080/v1/jobs/<job_id>
curl -sS -H "X-Science-Token: ${SCIENCE_TOKEN}" http://127.0.0.1:18080/v1/jobs/<job_id>/metrics
curl -sS -H "X-Science-Token: ${SCIENCE_TOKEN}" http://127.0.0.1:18080/v1/jobs/<job_id>/artifacts
```

응답에는 `jobId`, `kubeflowRunId`, Kueue 입장 상태, Pipeline 상태가 포함된다. 대기 원인은 다음으로 확인한다.

```bash
kubectl -n tenant-etri describe workload <workload-name>
kubectl -n tenant-etri describe job <job-name>
```

## Log와 Audit

```bash
kubectl -n tenant-etri logs deploy/science-job-api
kubectl -n tenant-etri logs deploy/agent-runtime
kubectl -n kubeflow logs deploy/ml-pipeline
kubectl -n kubeflow get workflows.argoproj.io
```

MCP Audit JSON에는 request ID, Tenant, Tool, 마스킹된 인자, 권한 결정, Job ID, 결과/오류가 남는다.

## GPU와 모니터링

```bash
kubectl get --raw '/api/v1/query?query=DCGM_FI_DEV_GPU_UTIL'
kubectl get --raw '/api/v1/query?query=DCGM_FI_DEV_FB_USED'
kubectl get pod -n tenant-etri -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.metadata.annotations.hami\.io/vgpu-devices-allocated}{"\n"}{end}'
kubectl -n kube-system port-forward svc/prometheus-operated 19090:9090
kubectl -n kube-system port-forward svc/prometheus-grafana 13000:80
```

HAMi Annotation과 DCGM Metric을 함께 확인한다. 논리 Memory/Core 비율은 실제 처리량·대역폭 격리와 같지 않다. Dashboard JSON은 `monitoring/grafana/science-ai-overview.json`이며 기존 Dashboard를 덮어쓰지 말고 별도 Import한다.

## 한국어 설명 페이지

```bash
kubectl -n science-ai-system port-forward --address=0.0.0.0 svc/mini-science-ai-os-ko-site 8088:80
curl -I http://127.0.0.1:8088/
```

현재 내부망 주소는 `http://192.168.0.56:8088`이다. 프로세스를 종료하면 공개도 종료된다.

설명 페이지 ConfigMap과 Deployment를 갱신할 때는 생성된 ConfigMap 이름 참조가 함께 바뀌도록 반드시 다음 명령을 사용한다.

```bash
kubectl apply -k apps/docs-site
```

## 장애 대응과 정리

- KFP 실패: `ml-pipeline`, `workflow-controller`, MySQL, MinIO 순으로 Event/Log를 확인한다.
- Queue 대기: Workload `Admitted` 조건과 `insufficient unused quota` 메시지를 확인한다.
- Artifact 실패: `kubeflow-artifact-store` Secret key 존재 여부, `seaweedfs` ExternalName, MinIO Bucket을 확인한다. 값을 출력하지 않는다.
- Demo만 정리: `make destroy-demo`.
- 일반 장애 조사에서 PVC를 삭제하지 않는다.
