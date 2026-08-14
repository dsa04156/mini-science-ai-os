# Permission map

| Subject | Namespace | 범위 |
|---|---|---|
| `science-job-api` | `tenant-etri` | ETRI KFP Run API 호출, ETRI Job/Pod/Workload 상태 조회 |
| `pipeline-runner-etri` | `kubeflow` + `tenant-etri` | ETRI Job 생성/조회/삭제, Pod Log, Workload 조회 |
| `science-job-runner` | `tenant-etri` | Kubernetes API 권한 없음, Token automount off |
| `agent-runtime` | `tenant-etri` | Science API HTTP만 사용, Secret/Kubernetes 권한 없음 |
| `resource-catalog` | `science-ai-system` | Node/Pod/Kueue의 Cluster Read-only |
| `kubeflow-minio-init` | `kubeflow` | API Token 없음, MinIO Bucket 초기화만 수행 |

Science 요청은 Namespace, ServiceAccount, Volume을 지정할 수 없다. 검증은 Agent의 Job/Pod/Secret 직접 조회가 `no`, Science API의 Secret 조회가 `no`, ETRI Runner의 default Namespace Job 생성이 `no`인지 확인한다.
