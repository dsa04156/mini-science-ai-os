# Variables and secrets

| 변수 | 기본값 | 의미 |
|---|---|---|
| `IMAGE_REGISTRY` | `192.168.0.56:5000` | 내부 Registry |
| `IMAGE_TAG` | `VERSION` 파일 값 (`0.3.1`) | Runtime Image Tag |
| `BUILD_IMAGES` | `1` | Bootstrap 시 Kaniko Build |
| `GITOPS_REPO_URL` | 빈 값 | Argo CD용 게시 Repository |
| `TENANT_MAX_CPU_MILLI` | `8000` | API Tenant CPU 상한 |
| `TENANT_MAX_MEMORY_BYTES` | `17179869184` | API Memory 상한 |
| `TENANT_MAX_GPU_COUNT` | `1` | API GPU Count 상한 |
| `JOB_TTL_SECONDS` | `86400` | 완료 Job 보존 시간 |
| `JOB_MAX_SECONDS` | `3600` | 최대 실행 시간 |
| `REQUIRE_IMAGE_DIGEST` | `false` | 운영에서 `true` 권장 |
| `PLATFORM_VERSION` | `0.3.1` | API/MCP/포털 표시 버전 |
| `PLATFORM_PROFILE` | `internal-production` | 내부 운영 제품 프로필 |
| `PORTAL_ACCESS_MODE` | `trusted-network` | 사내망 자동 세션 모드 |
| `PORTAL_SESSION_TTL_SECONDS` | `28800` | HttpOnly 세션 만료 |
| `PORTAL_COOKIE_SECURE` | `false` | TLS 도입 후 반드시 `true` |
| `API_DOCS_ENABLED` | `false` | 제품 배포에서 OpenAPI UI 비공개 |
| `KFP_ENDPOINT` | `http://ml-pipeline.kubeflow.svc.cluster.local:8888` | 내부 KFP API |
| `KFP_RUNNER_SERVICE_ACCOUNT` | Tenant별 값 | KFP Runner SA |
| `HAMI_COUNT_RESOURCE` | `nvidia.com/gpu` | 실제 조사된 Count Resource |
| `HAMI_MEMORY_RESOURCE` | `nvidia.com/gpumem` | 실제 조사된 Memory Resource |
| `HAMI_CORE_RESOURCE` | `nvidia.com/gpucores` | 실제 조사된 Core Resource |

`ensure-secrets.sh`는 다음 Secret을 생성하거나 보존한다.

- `science-ai-mlops/platform-minio`: `access-key`, `secret-key`
- `kubeflow/kubeflow-artifact-store`: `accesskey`, `secretkey`
- `kubeflow/mysql-secret`: `username`, `password`
- `tenant-etri/tenant-api-token`: `token`

값은 출력하거나 Git에 기록하지 않는다. 운영에서는 ExternalSecret 등 승인된 Secret Manager로 교체한다.
