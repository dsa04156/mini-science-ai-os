# Phase 5 evidence — Kubeflow Pipelines, MySQL and MinIO

이 문서는 2026-08-10의 Kubeflow 전환 이후 상태다. 이전 Tracking Runtime 결과는 과거 시점 Evidence에만 남아 있으며 현재 배포에는 존재하지 않는다.

## 1. 변경 파일

- `apps/kubeflow/cluster-scoped`, `runtime`, `tenant-launchers`
- `apps/mlops/minio.yaml`, `networkpolicy.yaml`
- `services/science_os/kfp_pipeline.py`, `kfp_launcher.py`, `job_api.py`, `demo.py`
- `requirements.txt`, `scripts/bootstrap.sh`, `validate.sh`, `test.sh`
- `docs/architecture.md`, `reproducibility.md`, `runbook.md`

## 2. 실행 명령

```text
rtk kubectl apply --server-side -k apps/kubeflow/cluster-scoped
rtk bash scripts/ensure-secrets.sh
rtk kubectl apply --server-side -k apps/kubeflow/runtime
rtk kubectl apply --server-side -k apps/kubeflow/tenant-launchers
rtk make validate
rtk make test
rtk kubectl get --raw /.../ml-pipeline:8888/proxy/apis/v2beta1/healthz
rtk kubectl exec tenant API -- GET /v1/jobs/<id>/{metrics,artifacts}
```

## 3. 실제 결과

- KFP Health: `tag_name=2.17.0`, `multi_user=false`, `pipeline_store=database`.
- `ml-pipeline`, UI, Metadata, MySQL, Workflow Controller가 모두 `1/1 Available`.
- 최종 CPU Job `416f16b638f9`, KFP Run `51003f6a-feca-4114-ad22-2ff05d42a731`, Workflow `mini-science-job-w4h75`가 `Succeeded 3/3`.
- Image `0.2.4`, Dataset `final-v1`, Metric `loss=0.125`, `accuracy=0.875`, Artifact root `s3://kubeflow-pipelines/v2/artifacts`를 API로 재조회했다.
- MinIO PVC와 MySQL PVC가 `local-path`에서 Bound. 이전 PostgreSQL StatefulSet/Service/Secret은 제거했고 PVC만 복구 유예용으로 보존했다.
- 활성 Deployment/Service/Pod 검색 결과: `NO_ACTIVE_MLFLOW_RESOURCES`.

## 4. 문제와 위험

- KFP 2.17.0 PostgreSQL Overlay는 API의 MySQL 형식 `?` Placeholder와 Cache Server Driver 문제로 실패했다. DB는 공식 MySQL 경로로 전환하고 Pipeline Caching을 비활성화했다.
- Artifact Launcher에는 내부 Endpoint, Region, Credential, `forcePathStyle` 설정이 모두 필요했다. 누락 시 AWS Endpoint 또는 Virtual-host DNS로 잘못 연결됐다.
- MySQL/MinIO는 Node-local Storage이므로 HA/DR이 아니다.
- KFP Standalone UI/API는 최종 사용자 인증이 없어서 ClusterIP로만 유지한다.

## 5. 다음 Phase

Science Job API와 MCP는 검증된 KFP Run ID/Metric/Artifact 경로를 사용한다. 운영 전 외부 Backup, OIDC Proxy, 정책 Enforcement CNI가 필요하다.
