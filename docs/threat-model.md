# Threat model

## 보호 자산

- KFP Run/Metadata, Model·Checkpoint·Plot Artifact.
- Tenant Job Spec, Log, GPU 할당, Quota 상태.
- API/MCP Token, MySQL/MinIO Credential.
- Agent Tool Call과 Job ID를 연결한 Audit Record.

| 경계 | 위협 | 통제 | 잔여 위험 |
|---|---|---|---|
| 연구자 → ETRI API | 임의 Namespace 지정, 과대 자원, 악성 Image | ETRI Namespace 고정, Pydantic, Allowlist, 상한 | 중앙 사용자 Identity 없음 |
| API → KFP | 임의 Pipeline/SA 실행 | 서버 내부 고정 Pipeline 함수와 Runner SA | API Image Supply-chain |
| KFP → Tenant | Runner가 타 Tenant 접근 | Tenant별 SA와 Namespace RoleBinding | KFP Control Plane 침해 |
| Job → Node | Host/Kubernetes Credential 탈취 | Restricted Context, hostPath/host namespace 금지, Token automount off | Runtime/Kernel 취약점 |
| Workload → Control Plane | Secret/다른 Namespace 조회 | 최소 RBAC, ServiceAccount Token 비활성 | Flannel Policy Enforcement BLOCKED |
| KFP → MinIO/MySQL | Credential 노출·데이터 손실 | Secret Ref, ClusterIP, PVC | local-path, Backup 미구성 |
| Agent → MCP | 타 Job 조회/취소, Log Secret 노출 | Tenant Token, API Scope, 재귀 Masking, Audit | Per-user 권한 없음 |
| GPU Workload → GPU | Noisy Neighbor, 잘못된 격리 주장 | Kueue+HAMi+DCGM 동시 관찰 | 논리 Quota ≠ 성능 격리 |

## 주요 Abuse Test

1. privileged/hostPath 필드 요청은 API 422.
2. 허용되지 않은 Registry는 API 400.
3. ETRI Agent의 Kubernetes Job/Pod/Secret 직접 조회는 RBAC `no`.
4. Agent에는 Kubernetes Credential/Client가 없어 직접 Cluster API를 호출하지 못함.
5. Job ServiceAccount Token은 자동 Mount하지 않음.

운영 전 OIDC, Signed Image/Admission Policy, 정책 Enforcement CNI, External Secret Manager, Immutable Audit Sink, 외부 Backup, CVE Scan이 필요하다.
