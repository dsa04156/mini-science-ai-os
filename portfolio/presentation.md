# 10분 전공면접 발표안

발표 제목: **과학 연구자를 위한 GPU·MLOps·Agent 통합 실행 플랫폼 설계와 검증**

핵심 메시지는 “기술을 나열한 것이 아니라, 연구자가 안전하게 작업을 제출하고
운영자가 재현 가능한 증거로 통제할 수 있는 하나의 흐름을 만들었다”이다.

## 슬라이드 구성

| 시간 | 슬라이드 | 전달할 내용 | 보여줄 증거 |
|---:|---|---|---|
| 0:00-0:45 | 1. 문제 | 연구자가 Kubernetes·GPU·MLOps를 직접 다루면 권한, 재현성, 운영 복잡도가 커진다 | `README.md` 제품 문장 |
| 0:45-1:45 | 2. 목표와 경계 | 단일 ETRI Tenant 내부 제품, Science API를 실행 경계로 선택 | `docs/ADR/0001-*`, `0003-*` |
| 1:45-3:15 | 3. 아키텍처 | Portal/MCP → API → KFP → Job → Kueue/HAMi → GPU, Metric/Artifact 흐름 | `docs/architecture.md` |
| 3:15-4:30 | 4. GPU 운영 | Queue 입장, HAMi Memory/Core 논리 할당, DCGM 관측을 함께 사용 | GPU Demo Evidence |
| 4:30-5:45 | 5. MLOps | Run, Metric, Artifact, Model Version을 Job 수명주기와 연결 | Kubeflow/MLflow/Grafana Evidence |
| 5:45-7:00 | 6. Agent 안전성 | MCP에는 Kubernetes Credential이 없고 API가 Scope·Allowlist·Audit를 강제 | RBAC Negative Test, Audit JSON |
| 7:00-8:15 | 7. 운영 검증 | PDB, 2 Replica, 모니터링, Release Gate, 복구/장애 Drill 설계 | `portfolio/live-demo.md` |
| 8:15-9:20 | 8. 실패와 한계 | Flannel Policy, local-path DR, 대규모 GPU, MLflow 단일 인스턴스를 명시 | Verification Matrix |
| 9:20-10:00 | 9. NAIS 기여 | 중앙 Identity/Audit, 외부 저장소, 원격 DR과 다기관 확장 | 직무요건 매핑표 |

## 30초 시작 문장

“저는 NAIS 기술직을 단순한 서버 운영이 아니라 연구자가 GPU와 AI Agent를
안전하고 재현 가능하게 사용할 수 있도록 만드는 플랫폼 운영으로 이해했습니다.
이를 검증하기 위해 Kubernetes, Kueue, HAMi, Kubeflow와 MCP를 하나의 Science Job
흐름으로 통합했고, 성공 화면보다 권한 거부와 운영 한계를 함께 증거로 남겼습니다.”

## 예상 질문과 답변 축

| 질문 | 답변 축 |
|---|---|
| 왜 MLflow를 단일 인스턴스로 구성했나? | 이번 목표는 Run·Artifact·Model Registry 기능의 실제 동작 증명이다. HA는 외부 PostgreSQL/Object Storage와 복구 실증을 함께 설계할 운영 전환 단계로 분리했다. |
| HAMi가 GPU를 완전히 격리하는가? | 아니다. Memory/Core 요청은 Scheduler의 논리 통제이며, 성능 격리는 별도 Benchmark와 Hardware/Runtime 통제가 필요하다. |
| Agent가 위험한 명령을 실행하면? | MCP는 Kubernetes Credential이 없고 고정 API만 호출한다. API가 Image/Resource/Namespace/SA를 제한하며 감사 이벤트를 남긴다. 승인 Gate와 Sandbox Runtime은 다음 단계다. |
| 가장 큰 운영 위험은? | 사용자별 Identity 부재, local-path 데이터, NetworkPolicy 강제 미검증이다. 이 세 가지를 외부 공개 전 차단 조건으로 둔다. |
| 장애가 나면 무엇부터 보는가? | 사용자 증상 → API/MCP Ready → KFP/MySQL/MinIO → Kueue Workload Condition → Pod Event → GPU/DCGM 순서로 좁힌다. |

## 마무리 문장

“이 프로젝트의 결과는 모든 기능이 완성됐다는 주장이 아니라, 구현된 것과
검증되지 않은 것을 구분하면서 NAIS가 확장할 수 있는 안전한 운영 경계를 만든
것입니다. 입사 후에는 대규모 GPU·다기관·원격 DR 환경에서 이 경계를 확장하고
검증하겠습니다.”
