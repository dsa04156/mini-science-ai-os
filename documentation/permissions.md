# Permission map

## Scope source

There is one product scope: ETRI. `TENANT=etri`, `TENANT_NAMESPACE=tenant-etri`, `LOCAL_QUEUE=tenant-etri` and `KFP_RUNNER_SERVICE_ACCOUNT=pipeline-runner-etri` come from Kubernetes configuration, not client input.

| Resource / operation | Portal session | Direct API token | MCP | KFP runner | Job |
|---|---:|---:|---:|---:|---:|
| Read ETRI jobs/metrics/artifacts | allow | allow | via API | read execution objects | deny |
| Submit/cancel ETRI job | allow with Same-Origin write | allow | via API | create/delete Job only | deny |
| Select Namespace/SA/volume/security context | deny | deny | deny | fixed binding | deny |
| Read Kubernetes Secret | no Kubernetes access | no endpoint | no Kubernetes credential | deny | deny |
| Create Job outside `tenant-etri` | deny | deny | deny | RBAC deny | deny |
| Call Kubernetes API directly | n/a | n/a | deny | limited in-cluster RBAC | Token automount off |

The platform has no database row-level security layer. Scope is enforced by Namespace RBAC, fixed server configuration and API filtering. Current anonymous portal sessions are not individual user roles.
