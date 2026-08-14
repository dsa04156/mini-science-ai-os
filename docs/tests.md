# Test and coverage map

| 영역 | 검사 | 판정 |
|---|---|---|
| Python/API | compileall, pytest model/common/catalog/MCP/KFP launcher | 로컬 실행 결과 기록 |
| Manifest | Kustomize render, kubectl dry-run, 선택적 kubeconform | Render 실패 시 FAIL |
| Security | privileged/hostPath/host namespace 정적·HTTP 거부 | 400/422와 Manifest 검사 |
| Tenant RBAC | Cross-Tenant Job/Pod/Secret `auth can-i` | `no` 필요 |
| Kubeflow | API Health, Run/Workflow 상태, Metric/Artifact 응답 | 실제 성공 Run 필요 |
| Kueue | Quota 내 입장, 초과 Pending Reason | 실제 Condition 필요 |
| GPU | HAMi Annotation + 동일 GPU UUID + DCGM | 논리 공유만 PASS, 성능 격리 주장 금지 |
| MCP | HTTP initialize/list/call, 자기 Job, 타 Tenant 404 Audit | 실제 Log 필요 |
| Network | CNI와 외부/Cross-Tenant Probe | Enforcement CNI 없으면 BLOCKED |
| Argo CD | Application Synced/Healthy/Drift | 게시 Git URL 없으면 BLOCKED |

모든 명령 출력은 `docs/evidence/`에 기록한다. 도구 미설치나 환경 제약은 성공으로 바꾸지 않는다.
