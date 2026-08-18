# NAIS 기술직-1 직무요건-증거 매핑

대상은 2026년도 NAIS 제2차 정규직 `기술직-1 통합플랫폼연구/플랫폼개발`이다.
공식 [직무기술서](https://www.nst.re.kr/www/downloadBbsFile.do?atchmnflNo=11344)의
요구사항을 현재 저장소의 구현 및 검증 증거와 대조했다.

## 요약 판정

이 저장소는 Kubernetes 기반 GPU 작업 입장·배치, Kubeflow 기반 실행 이력,
Prometheus/DCGM 관측, MCP Agent 경계와 감사 로그를 하나의 Science Job 흐름으로
통합한다. 이는 공고의 핵심 업무와 직접 대응한다. SLURM은 현재 범위에서 제외했고,
대규모 GPU 환경, 원격 백업 복구, MLflow 고가용성 운영 경험은 증명하지 않는다.

## 요구사항 추적표

| 공고 요구사항 | 구현 | 검증 증거 | 상태 | 남은 한계 |
|---|---|---|---|---|
| Linux/GPU 클러스터 운영 | HAMi 리소스와 Kubernetes GPU Job, DCGM 수집 | `docs/evidence/verification-matrix.md`, `docs/evidence/demo-*` | VERIFIED | 2개 GPU Node의 실험실 규모이며 대규모 운영은 아님 |
| 자원 스케줄링 및 HPC | Kueue Queue/Quota와 HAMi GPU 배치 | `scripts/demo.sh`, `docs/evidence/verification-matrix.md` | VERIFIED | Kubernetes 경로만 검증했으며 SLURM은 현재 범위에서 제외 |
| Docker/Kubernetes 및 CI/CD | Kustomize, 고정 이미지 Digest, 배포·검증 Make Target | `scripts/validate.sh`, `.github/workflows/portfolio.yml` | IMPLEMENTED | Argo CD는 게시 Git URL 부재로 Sync 미검증 |
| MLOps 운영 | Kubeflow Pipelines 2.17 CPU component가 MLflow 3.13 Run/Artifact/Model candidate 생성 | `docs/evidence/verification-matrix.md`, `portfolio/mlflow-grafana-demo/evidence.md` | VERIFIED (기능 PoC) | MLflow는 SQLite/local-path 단일 인스턴스이며 W&B는 미검증 |
| Prometheus/Grafana 모니터링 | Prometheus, DCGM, KFP 실행 상태와 Grafana 자동 프로비저닝 Dashboard | `portfolio/mlflow-grafana-demo/evidence.md`, `portfolio/mlflow-grafana-demo/evidence/grafana-kfp-mlflow-dashboard.png` | VERIFIED | Alert 외부 전달과 장기 보존은 미검증 |
| LLM Agent/MCP 실행환경 | MCP Tool 6개, Science API 경계, Kubernetes Credential 제거 | `services/science_os/mcp_server.py`, `scripts/test.sh` | VERIFIED | 컨테이너 Sandbox Runtime 및 승인 Gate는 미구현 |
| 도구 호출·실행 격리·로그 | Namespace/SA 고정, 입력 Allowlist, non-root Job, 구조화 Audit | `docs/permissions.md`, `docs/threat-model.md`, `tests/test_mcp.py` | VERIFIED | 사용자별 Identity와 중앙 Audit 보존은 없음 |
| 백업·복구 | Git 재생성 절차와 격리 Restore Drill Script | `docs/disaster-recovery.md`, `portfolio/scripts/recovery-drill.sh` | IMPLEMENTED | 원격 Backup, PITR, 실제 Restore 성공 증거는 없음 |
| 접근 통제·감사·취약점 관리 | RBAC Negative Test, Secret Ref, 정적 보안 Gate | `tests/test_manifest_security.py`, `portfolio/scripts/security-check.sh` | IMPLEMENTED | Flannel NetworkPolicy 강제 및 외부 Scanner 결과는 미검증 |
| 장애 탐지·복구 | 2 Replica/PDB, 상태 점검, 안전한 Pod 교체 Drill | `portfolio/scripts/resilience-drill.sh` | IMPLEMENTED | KFP/MySQL/MinIO는 Single Instance |
| 플랫폼 아키텍처 설계·최적화 | Adapter 경계, ADR, Flow/Permission/Test Map | `docs/architecture.md`, `docs/ADR/`, `documentation/` | VERIFIED | Multi-site Federation은 미래 범위 |
| 오픈소스 활동 | 재현 가능한 코드·문서·테스트 구조 | 저장소 전체 | IMPLEMENTED | 공개 저장소의 Issue/PR/외부 기여 이력은 별도 필요 |

## 면접에서 지켜야 할 주장 경계

### 말할 수 있는 것

- 실제 Kubernetes 클러스터에서 CPU/GPU Science Job을 제출하고 Kueue 입장,
  HAMi 논리 GPU 할당, Kubeflow Run/Metric/Artifact까지 확인했다.
- Agent가 Kubernetes API를 직접 호출하지 않고 Tenant Science API만 사용하도록
  권한 경계를 설계하고 부정 테스트를 수행했다.
- 운영 한계를 `PASS`, `PARTIAL`, `BLOCKED`로 분리하고 실행 증거를 저장했다.

### 말하면 안 되는 것

- HAMi 논리 할당을 물리 GPU 성능 격리라고 주장하지 않는다.
- Kubernetes 실증을 SLURM 또는 대규모 HPC 운영 경험이라고 표현하지 않는다.
- Manifest가 있다는 이유만으로 Flannel NetworkPolicy가 강제된다고 주장하지 않는다.
- `local-path` PVC를 고가용성 저장소나 재해복구 완료 상태라고 표현하지 않는다.

## 보완 우선순위

1. 외부 PostgreSQL/Object Storage와 원격 Backup을 사용한 MLflow 복구 실증
2. Cilium/Calico 환경의 Cross-Namespace NetworkPolicy Negative Test
3. Grafana Alert 외부 전달 경로 검증
4. 공개 Git 저장소에서 CI, Argo CD Sync, Issue/PR 이력 확보
5. 더 많은 Node/GPU에서 Kueue Queue·Quota 부하 실증
