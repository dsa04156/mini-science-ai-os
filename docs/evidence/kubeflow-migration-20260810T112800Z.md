# Kubeflow migration and live verification — 2026-08-10

## 변경 범위

- Runtime: Kubeflow Pipelines `2.17.0`, 포함 Argo Workflows `v4.0.5`, KFP Metadata, MySQL 8.4 Digest 고정.
- Artifact: 기존 MinIO를 `seaweedfs.kubeflow.svc` ExternalName으로 재사용, Bucket `kubeflow-pipelines`.
- API/MCP: KFP Run 제출·조회, Metric/Artifact 반환, Tenant Runner SA, Audit `linked_job_id`.
- 제거: 이전 Tracking Deployment/Service/Secret/NetworkPolicy와 사용하지 않는 PostgreSQL StatefulSet/Service/Secret. PVC는 삭제하지 않음.

## 실제 검증 출력

### KFP Health와 Runtime

```text
$ kubectl get --raw '/api/v1/namespaces/kubeflow/services/http:ml-pipeline:8888/proxy/apis/v2beta1/healthz'
{"commit_sha":"714d7e4a76085ff2cc107c4e26c18c38c14dbcaa","tag_name":"2.17.0","multi_user":false,"pipeline_store":"database"}

metadata-grpc-deployment  1  1
ml-pipeline               1  1
ml-pipeline-ui            1  1
mysql                     1  1
workflow-controller       1  1
```

### 최종 0.2.4 CPU E2E

```text
jobId: 416f16b638f9
kubeflowRunId: 51003f6a-feca-4114-ad22-2ff05d42a731
workflow: mini-science-job-w4h75  Succeeded  3/3
Kueue: Quota reserved in ClusterQueue science-shared; Admitted=True
metrics: loss=0.125, accuracy=0.875, duration_seconds=0.40079689025878906
artifact image: 192.168.0.56:5000/mini-science-ai-os:0.2.4
artifact dataset_version: final-v1
pipelineRoot: s3://kubeflow-pipelines/v2/artifacts
KFP state: SUCCEEDED
```

### HAMi GPU 공유와 DCGM

```text
science-1b082b767f93-nxvh5 scheduler=hami-scheduler
  hami=GPU-322e2753-8411-28a6-ab7b-bb03d5ba0dac,NVIDIA,1024,10:;
science-e7e9d06251b2-q52mh scheduler=hami-scheduler
  hami=GPU-322e2753-8411-28a6-ab7b-bb03d5ba0dac,NVIDIA,1024,10:;
node=etri-ser0001-cg0msb
DCGM_FI_DEV_GPU_UTIL UUID=GPU-322e... model=NVIDIA GeForce RTX 5060 Ti value=2
```

두 KFP Workflow는 모두 `Succeeded 3/3`이었다. 동일 GPU UUID에 각 1024MiB/10%가 논리 할당된 사실만 검증했으며 성능 격리는 검증하지 않았다.

### Queue Quota 대기

```text
science-aa1f2eac7d36 (3 CPU): Running, Admitted=True
science-6d40f2a2bc94 (6 CPU): Suspended
couldn't assign flavors to pod set main: insufficient unused quota for cpu in flavor science-cloud, 1 more needed
```

확인 후 두 Job을 Science API DELETE로 취소했고 `QUEUE_TEST_RESOURCES_CLEANED`를 확인했다.

### Tenant와 MCP

```text
ETRI/KIST cross-namespace jobs,pods,secrets: 모두 no
unauthenticated GET: 401
cross-tenant token: 401
disallowed image: 400
privileged input: 422
hostPath input: 422
ETRI Agent GET KIST job c0ac5d02f31d: HTTP 404
audit error=HTTPStatusError linked_job_id=c0ac5d02f31d
```

KIST 소유 Job `c0ac5d02f31d` 자체는 KFP Run `4c114f19-7ca4-4ea2-b12b-a11f6716489e`에서 `SUCCEEDED`였다.

### 코드/Manifest와 제거 상태

```text
pytest: 11 passed in 0.80s
Kustomize/client validation: PASS
forbidden host/privileged fields: none
active Deployment/Service/Pod search: NO_ACTIVE_MLFLOW_RESOURCES
science-ai-mlops runtime: MinIO 1/1; data-minio-0 Bound
legacy data-postgres-0 PVC: Bound, runtime에서 미사용·삭제하지 않음
```

### 한국어 HTML

```text
LISTEN 0 4096 0.0.0.0:8088 0.0.0.0:* users:(("kubectl",pid=1161969,fd=7))
HTTP 200
page markers: image 0.2.4 / Kubeflow Pipelines / 11 passed
URL: http://192.168.0.56:8088
```

## 실제 실패와 조정

1. KFP PostgreSQL 경로에서 `pgx` 설정 후에도 MySQL 형식 Placeholder SQL이 발생했다.
2. Cache Server 2.17.0은 `pgx`를 지원하지 않아 Caching을 끄고 Cache Server를 제거했다.
3. Artifact Endpoint의 Namespace 변수 미확장, Region/Credential 누락, AWS 기본 Endpoint, Virtual-host DNS 실패를 순서대로 확인했다.
4. 최종 KFP Launcher S3 Provider에 내부 Endpoint, `us-east-1`, Secret, `forcePathStyle=true`를 명시해 해결했다.
5. 다중 문서 Strategic Delete Patch는 Kubernetes 1.31 내장 Kustomize SIGSEGV를 일으켰다. Deployment/Service 삭제 Patch를 파일별로 분리해 Render와 Apply를 통과했다.

## 남은 BLOCKED

- NetworkPolicy: Flannel 환경에서 Enforcement Controller를 찾지 못해 실제 차단 보장 불가.
- Argo CD: App-of-Apps 3개 Manifest는 작성했지만 게시 Git Repository URL이 없어 실제 Synced/Healthy 미검증.
- Grafana: Dashboard JSON 갱신 완료, 기존 Grafana UI Import는 미실행.
