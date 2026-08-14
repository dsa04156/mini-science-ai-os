@/home/etri/.codex/RTK.md

# mini-science-ai-os 작업 지침

## 프로젝트 목적과 현재 범위

- 이 저장소는 ETRI 단일 테넌트 내부망용 Science Workspace다.
- 연구자와 Agent는 Kubernetes API나 임의 PodSpec을 직접 사용하지 않는다. Portal/MCP는 인증된 Science Job API를 호출하고, API가 Tenant·Namespace·ServiceAccount·Queue·Image·Resource 범위를 강제한다.
- Kubeflow Pipelines는 실행 이력·Metric·Artifact를, Kueue는 입장과 Quota를, HAMi는 GPU 논리 할당을 담당한다.
- 실제 다기관 Federation, 실제 SLURM/Cloud 제출, 외부 TLS/OIDC, 원격 DR은 완료된 기능으로 표현하지 않는다.
- 화면과 문서에서 실제 관측값, 보존된 검증 증거, PoC와 계획을 명확히 구분한다. 데모 값을 실제 장비 상태처럼 꾸미지 않는다.

## 소스와 소유권

- 기본 제품 소스는 `services/`, `tenants/`, `apps/`, `policies/`, `clusters/`에 있다.
- 현재 운영 대시보드와 `/v1/operations` 릴리스의 재현 소스는 `workspace-topology/` Overlay다. 이 Overlay는 backend override, Portal asset, 고정 이름 ConfigMap, Kaniko build와 배포 절차를 함께 소유한다.
- `open-source-docs/`가 내부 문서 웹의 선언형 소스고, `portfolio/`가 NAIS 채용 증거 패키지다.
- 선언형 소스가 있는 Kubernetes 리소스를 라이브 클러스터에서만 수정해 drift를 만들지 않는다. 긴급 라이브 수정이 필요했다면 같은 작업에서 소스에도 반영하고 차이를 검증한다.
- 사용자의 기존 변경을 보존한다. 작업 범위 밖의 파일을 되돌리거나 정리하지 않는다.

## 실제 장비와 클러스터 안전

- 조사와 진단은 읽기 전용 명령부터 시작한다. 변경 전에 Namespace, Label, 소유자와 정확한 대상을 확인한다.
- 프로젝트가 소유하지 않은 Node, Namespace, Workload, HAMi/DCGM, Kueue, Kubeflow 또는 스토리지를 임의 변경·삭제하지 않는다.
- 삭제·복구·장애 훈련은 전용 스크립트의 확인 변수와 소유권 검사를 사용하고, 격리된 대상에서만 실행한다.
- 실제 GPU Job 제출은 자원 경합을 만들 수 있다. 사용자가 실행 검증을 요청했거나 기존 안전한 데모 절차가 명시된 경우에만 수행한다.
- Secret, Token, Cookie, kubeconfig, 개인 식별 정보를 출력·로그·스크린샷·Git·Semantica에 남기지 않는다.
- 브라우저와 Agent에 Kubernetes Credential을 전달하지 않는다. Resource Catalog의 cluster-wide read 경계와 Science API의 인증 Proxy를 유지한다.

## 구현 원칙

- 요청된 범위 안에서 가장 작은 일관된 변경을 한다. 기존 API 계약과 신뢰 경계를 바꾸기 전에는 관련 ADR, 문서와 Semantica 선행 결정을 확인한다.
- 동적 HTML은 반드시 escaping하고 CSP를 깨는 inline style/script를 새로 만들지 않는다.
- 새 Workload는 non-root, privilege escalation 금지, capability drop, RuntimeDefault seccomp, 자원 request/limit과 ServiceAccount token 최소화를 기본으로 한다.
- 실시간 상태를 가져오지 못했을 때 0이나 정상으로 위장하지 않고 `unknown`, `unavailable` 또는 degraded 상태를 표시한다.
- 운영 수치와 상태는 시간에 따라 변한다. 문서에 고정 수치를 쓸 때는 관측 시점과 출처를 적는다.

## 기본 작업 흐름

1. `git status -sb`로 브랜치와 기존 변경을 확인한다.
2. 중요한 작업이면 Semantica 요약, 관련 결정과 미해결 위험을 조회한다.
3. 관련 소스·테스트·배포 Manifest를 함께 읽고 변경 범위를 정한다.
4. 코드와 필요한 테스트·문서를 함께 변경한다.
5. 아래 검증을 위험도에 맞게 실행하고 실제 출력을 확인한다.
6. 배포가 요청된 경우에만 선언형 소스로 배포하고 Rollout·Endpoint·브라우저를 검증한다.
7. Git 게시가 요청되면 전용 `agent/<설명>` 브랜치와 PR을 사용한다. main 직접 커밋·푸시는 하지 않으며, 명시적 병합 요청과 성공한 원격 체크가 있을 때만 병합한다.

## 검증 기준

- 모든 변경: `git diff --check`
- 제품·포트폴리오: `make portfolio-check`
- Python 변경: 관련 `pytest`와 `python3 -m compileall`
- Portal JavaScript 변경: `node --check <파일>`
- Manifest 변경: 관련 경로의 `kubectl kustomize <경로>`
- `workspace-topology/` 변경: `workspace-topology/tests/test_topology.py`를 base package와 override를 합친 격리 환경에서 실행한다.
- UI 변경: 실제 브라우저로 데스크톱과 390px 모바일을 확인하고, 가로 overflow·console error·핵심 이동 경로를 검사한다.
- 실제 배포: Deployment Ready replica, 사용 이미지, `/v1/operations`, 주요 Ingress HTTP 상태를 확인한다. Rollout 직후 Prometheus scrape 지연은 잠시 degraded로 보일 수 있으므로 다음 scrape까지 재확인한다.
- 완료, 통과, 배포 성공을 말하기 직전에 관련 검증 명령을 새로 실행한다. 경고와 미검증 범위도 함께 보고한다.

## 배포 기준

- 운영 대시보드 이미지 build/deploy는 `workspace-topology/README.md`와 `workspace-topology/deploy.sh`를 따른다.
- 내부 문서 웹은 `open-source-docs/` Kustomize를 사용한다. 이미지가 포함된 ConfigMap은 Kubernetes apply annotation 크기 제한을 넘지 않도록 최적화한다.
- 배포 이미지 Tag와 Digest를 기록하고, ConfigMap으로 mount되는 Portal asset과 이미지 내부 소스가 일치하는지 확인한다.
- Kaniko build Pod가 UID 0과 일부 filesystem capability를 요구하는 현재 위험을 숨기지 않는다. 일반 Runtime Workload에 같은 권한을 확장하지 않는다.

## 알려진 운영 경계

- 현재 제품은 승인된 내부망의 `trusted-network` 모델이다. 외부망 공개 전 TLS, OIDC/PKCE, 사용자별 감사와 rate/abuse 통제를 추가한다.
- Flannel-only 환경의 NetworkPolicy enforcement, local-path 기반 MySQL/MinIO의 원격 DR, 실제 SLURM/Federation 제출은 미검증 또는 후속 범위다.
- HAMi Memory/Core 값은 논리 할당이며 성능 격리 보장이 아니다. 물리 사용량은 DCGM과 함께 판단한다.

## Semantica 영속 기억

- 중요한 작업을 시작할 때 Semantica 그래프 요약을 확인하고, 현재 작업과 관련된 과거 결정 및 미해결 위험을 조회한 뒤 계획한다.
- 기존 아키텍처, 범위, 제약 또는 인터페이스를 변경하려는 시점에는 관련 선행 결정을 다시 조회해 충돌 여부를 확인한다.
- 중요한 작업의 최종 답변을 작성하기 전에 이번 작업에서 확정된 요구사항, 설계 결정과 근거, 검증 결과, 남은 위험을 Semantica에 기록한다.
- 대화 전문, 임시 추론, 자격 증명, 비밀정보, 개인정보 또는 검증되지 않은 주장은 저장하지 않는다.
- 저장할 영속 정보가 없으면 기록을 만들지 않는다. Semantica를 사용할 수 없으면 기록한 것처럼 말하지 말고 최종 답변에 해당 사실을 알린다.
