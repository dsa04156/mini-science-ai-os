# Variables and secrets

| Name | Used by | Scope | Source | Rotation | Risk |
|---|---|---|---|---|---|
| `TENANT_API_TOKEN` | API, MCP | server | `tenant-etri/tenant-api-token` | replace Secret, restart API/MCP | Signs portal sessions and authenticates direct API |
| `PLATFORM_MINIO_ACCESS_KEY`, `PLATFORM_MINIO_SECRET_KEY` | MinIO/KFP | server | `science-ai-mlops/platform-minio` | coordinated Secret and workload rotation | Artifact disclosure/loss |
| `KUBEFLOW_MYSQL_PASSWORD` | KFP MySQL | server | `kubeflow/mysql-secret` | maintenance window | Run metadata disclosure/loss |
| `PLATFORM_VERSION` | API/MCP/UI | server/public metadata | Manifest | release | Drift if not aligned with `VERSION` |
| `PORTAL_ACCESS_MODE` | API | server | Manifest | deploy | `trusted-network` 사용자에게 ETRI 권한 부여 |
| `PORTAL_SESSION_TTL_SECONDS` | API | server | Manifest | deploy | Longer stolen-cookie window |
| `PORTAL_COOKIE_SECURE` | API | server | Manifest | set true with TLS | False allows HTTP cookie transport |
| `ALLOWED_REGISTRIES` | API | server/public config | Manifest | deploy | Broad registry permits unreviewed images |
| `REQUIRE_IMAGE_DIGEST` | API | server | Manifest | deploy | False permits mutable tags |
| `GITOPS_REPO_URL` | bootstrap | operator | environment | repository change | Incorrect URL prevents reconciliation |

No secret is bundled in portal HTML/JavaScript or stored in Git. `ensure-secrets.sh` preserves existing values and does not print them.

## Pre-go-live checklist

- 사내망 범위가 바뀌면 Traefik `ipAllowList`를 승인된 CIDR로 갱신한다.
- 외부 공개 또는 사용자별 실명 감사가 필요하면 OIDC/TLS와 `Secure` Cookie를 도입한다.
- Set `REQUIRE_IMAGE_DIGEST=true`; sign and verify approved images.
- Move all credentials to the approved external Secret manager and test rotation.
- Configure immutable audit export and MySQL/MinIO backup restore tests.
- Confirm a NetworkPolicy-enforcing CNI and run live deny probes.
