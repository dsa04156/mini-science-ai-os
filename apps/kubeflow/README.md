# Kubeflow Pipelines runtime

Kubeflow Pipelines `2.17.0`을 고정된 Git Tag로 배포한다. KFP가 포함한 Argo Workflows와 Metadata를 사용하고, DB는 Digest 고정 MySQL 8.4, Artifact는 프로젝트 MinIO의 `kubeflow-pipelines` Bucket을 사용한다. Credential은 `scripts/ensure-secrets.sh`가 생성하며 Git에 값이 없다.

```bash
kubectl apply --server-side -k apps/kubeflow/cluster-scoped
bash scripts/ensure-secrets.sh
kubectl apply --server-side -k apps/kubeflow/runtime
kubectl apply --server-side -k apps/kubeflow/tenant-launchers
```

Upstream KFP 2.17.0의 PostgreSQL 경로는 API Query Placeholder와 Cache Server Driver 호환 문제로 사용하지 않았다. Pipeline Caching은 비활성화했으며 Cache Server Deployment/Service를 Overlay에서 제거한다.

Standalone KFP API/UI에는 사용자 인증이 없으므로 ClusterIP로만 유지한다. 운영자는 `kubectl -n kubeflow port-forward svc/ml-pipeline-ui 8080:80`로 점검한다.
