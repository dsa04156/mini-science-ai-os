# 이 프로젝트는 도대체 뭘 하는 걸까요?

## 아주 쉬운 Science AI OS 이야기

이 문서는 컴퓨터를 잘 모르는 사람도 mini-science-ai-os가 무엇인지 이해할 수 있도록 만든 설명서다.

같은 내용을 오픈소스 프로젝트 문서 화면으로 읽으려면 `http://mini-science-ai-os.192.168.0.56.nip.io/`를 연다.

먼저 딱 한 문장으로 말하면:

> 연구자가 어려운 컴퓨터 명령을 외우지 않아도, 화면에서 실험을 부탁하고 결과를 찾아볼 수 있게 도와주는 연구 실험 놀이터다.

이름은 조금 어렵지만 겁낼 필요가 없다. 하나씩 보면 모두 익숙한 역할이다.

---

## 1. 왜 이런 것이 필요할까요?

연구자 민지가 있다고 생각해 보자.

민지는 인공지능 실험을 하고 싶다.

- 사진을 보고 불량품을 찾는 실험
- 많은 숫자를 빠르게 계산하는 실험
- GPU를 사용하는 실험
- 어제 한 실험과 오늘 한 실험을 비교하는 일

그런데 실험을 시작하려면 원래 아주 많은 것을 알아야 한다.

- 어느 컴퓨터가 비어 있는가?
- CPU와 메모리는 얼마나 필요한가?
- GPU를 누가 사용하고 있는가?
- 내 차례는 언제인가?
- 프로그램은 어디서 실행해야 하는가?
- 결과 파일은 어디에 저장되는가?
- 실패했다면 어디서 이유를 찾아야 하는가?

민지가 이 모든 일을 직접 하면 연구보다 컴퓨터 관리에 더 많은 시간을 쓰게 된다.

그래서 이 프로젝트가 대신 말한다.

> “민지야, 하고 싶은 실험만 알려 줘.  
> 컴퓨터 찾기, 순서 정하기, 실행하기, 기록하기는 우리가 도와줄게.”

그 도우미 묶음이 Science AI OS다.

---

## 2. 가장 쉬운 비유: 연구 놀이터

커다란 연구 놀이터가 있다고 생각해 보자.

놀이터에는 여러 친구와 선생님이 있다.

| 이야기 속 역할 | 하는 일 | 실제 기술 이름 |
|---|---|---|
| 연구하는 친구 | 하고 싶은 실험을 고른다 | 연구자 |
| 안내 화면 | 실험 내용을 적고 결과를 본다 | Science Workspace |
| 접수 선생님 | 위험하거나 이상한 부탁인지 검사한다 | Science Job API |
| 도우미 로봇 | 사람 대신 접수 선생님에게 부탁한다 | MCP Agent Runtime |
| 번호표 기계 | 누구 차례인지 정한다 | Kueue |
| 자리 배정 선생님 | 어느 컴퓨터에서 할지 정한다 | Kubernetes Scheduler |
| GPU 케이크 나누기 선생님 | GPU 사용량을 논리적으로 나눈다 | HAMi |
| 실험 순서 공책 | 실험 단계를 실행하고 기록한다 | Kubeflow Pipelines |
| 준비물 상자 | 실행할 프로그램을 담는다 | Container Image |
| 작품 보관 창고 | 결과 파일을 저장한다 | MinIO |
| 도서관 색인 | 어떤 실험과 결과가 있는지 기록한다 | MySQL·Metadata |
| 건강 확인 선생님 | 컴퓨터와 GPU 상태를 지켜본다 | Prometheus·DCGM |
| 상황판 | 상태를 그림으로 보여준다 | Grafana |
| 놀이터 정문 | 올바른 주소로 안내하고 외부 접근을 막는다 | Traefik |
| ETRI 전용 교실 | 다른 팀과 공간을 나눈다 | tenant-etri Namespace |

이 친구들이 서로 손을 잡고 한 가지 실험을 끝까지 도와준다.

---

## 3. 내가 버튼을 누르면 무슨 일이 일어날까요?

민지가 Science Workspace에서 새 작업 버튼을 누른다고 생각해 보자.

전체 흐름은 이렇다.

    연구자
      ↓ 실험 부탁
    Science Workspace
      ↓ 안전한 요청
    Science Job API
      ↓ 실행 기록 만들기
    Kubeflow Pipelines
      ↓ 실제 작업 만들기
    Kueue 번호표
      ↓ 차례가 오면
    Scheduler와 HAMi
      ↓ 컴퓨터와 GPU 자리 배정
    Kubernetes Job 실행
      ↓
    Metric과 Artifact 저장
      ↓
    Science Workspace에서 결과 확인

이제 한 칸씩 자세히 보자.

### 3-1. 민지가 실험 신청서를 쓴다

민지는 화면에 다음과 같은 것을 적는다.

- 실험 이름
- 사용할 프로그램 상자
- CPU와 메모리 양
- GPU가 필요한지
- 데이터셋 버전
- 실행할 명령

이것은 놀이 신청서와 비슷하다.

### 3-2. 접수 선생님이 신청서를 검사한다

Science Job API는 다음을 확인한다.

- 허락된 프로그램 상자인가?
- CPU를 너무 많이 달라고 하지 않았나?
- GPU 숫자가 규칙 안에 있는가?
- 몰래 관리자 권한을 달라고 하지 않았나?
- 다른 팀 교실에 들어가려 하지 않았나?

이 검사를 통과하지 못하면 실행하지 않고 이유를 알려 준다.

중요한 점은 연구자가 Kubernetes에 마음대로 명령하지 않는다는 것이다. 반드시 이 접수창구를 지난다.

### 3-3. 실험 공책에 새 페이지를 만든다

Kubeflow Pipelines는 새 실험 페이지를 만든다.

공책에는 이런 것이 기록된다.

- 누가 어떤 실험을 부탁했는가?
- 어떤 순서로 실행했는가?
- 성공했는가, 실패했는가?
- 어떤 숫자 결과가 나왔는가?
- 어떤 파일이 만들어졌는가?

나중에 같은 실험을 다시 찾거나 비교할 수 있다.

### 3-4. 번호표를 받는다

Kueue는 작업에 번호표를 준다.

컴퓨터가 비어 있고 사용 가능한 양이 충분하면 들어가도 좋다고 말한다.

자원이 부족하면 작업을 버리지 않는다. 줄에 세워 두고 기다리게 한다.

그래서 Pending은 항상 고장이라는 뜻이 아니다.

> “망가졌어요”가 아니라 “아직 네 차례가 아니야”일 수도 있다.

### 3-5. 실행할 자리를 정한다

Kubernetes Scheduler는 어느 컴퓨터에서 작업할지 정한다.

- CPU가 충분한가?
- 메모리가 충분한가?
- 필요한 GPU가 있는가?
- 해당 컴퓨터가 건강한가?

GPU 작업이라면 HAMi도 도와준다.

### 3-6. GPU 케이크를 나눈다

GPU는 비싸고 힘이 센 계산 도구다.

아주 큰 케이크 하나를 여러 친구가 조금씩 나눠 먹는 모습을 떠올려 보자. HAMi는 한 작업에 GPU 메모리 1024MiB와 Core 10% 같은 논리적인 몫을 표시해 준다.

하지만 이 비유에는 중요한 한계가 있다.

케이크 조각 크기를 표시했다고 해서 먹는 속도까지 완벽하게 똑같아지는 것은 아니다. HAMi의 논리 할당은 실제 처리 속도나 대역폭을 완전히 보장하지 않는다.

### 3-7. 프로그램 상자를 열고 실험한다

Container Image는 준비물이 모두 들어 있는 밀봉 상자와 비슷하다.

상자 안에는 다음이 들어 있다.

- Python
- 필요한 프로그램
- 실험 코드
- 실행에 필요한 도구

어느 컴퓨터에서 열어도 비슷한 환경을 만들 수 있다.

Kubernetes Job은 이 상자를 열어 실제 실험을 수행한다.

### 3-8. 결과를 기록하고 보관한다

실험이 끝나면 두 종류의 결과가 생긴다.

Metric은 숫자로 된 성적표다.

- 정확도
- 손실값
- 실행 시간

Artifact는 만들어진 작품이다.

- 모델 파일
- 그래프
- 결과 표
- 로그
- 가공된 데이터

숫자는 Kubeflow 실행 기록과 연결되고, 파일은 MinIO 같은 보관 창고에 저장된다.

### 3-9. 민지가 화면에서 결과를 본다

민지는 다시 Science Workspace를 연다.

거기에서 다음을 볼 수 있다.

- 기다리는 중인지
- 실행 중인지
- 성공했는지
- 실패했는지
- 정확도가 얼마인지
- 어떤 결과 파일이 생겼는지

민지는 컴퓨터마다 찾아다니지 않아도 된다.

---

## 4. CPU와 GPU는 무엇이 다른가요?

### CPU는 여러 가지 일을 잘하는 똑똑한 일꾼

CPU는 일반적인 계산과 프로그램 실행을 잘한다.

이를테면 선생님 한 명이 읽기, 쓰기, 정리, 계산을 골고루 잘하는 것과 비슷하다.

이 프로젝트의 첫 CPU 데모는 아주 작은 계산을 하고 다음과 같은 결과를 만든다.

- mode: cpu
- loss: 약 0.125
- accuracy: 약 0.875

### GPU는 같은 계산을 아주 많이 하는 빠른 팀

GPU는 비슷한 계산을 한꺼번에 많이 하는 데 강하다.

아주 많은 블록을 동시에 분류하는 친구들이 줄지어 있는 것과 비슷하다.

인공지능 학습과 큰 행렬 계산에서 특히 유용하다.

이 프로젝트의 GPU 데모는 다음과 같은 결과를 만든다.

- mode: gpu
- loss: 약 0.095
- accuracy: 약 0.905

이 숫자는 실제 과학 성능을 증명하는 값이 아니라, 실행부터 기록까지 연결되는지 확인하는 데모 값이다.

---

## 5. 왜 그냥 빈 컴퓨터에서 바로 실행하지 않나요?

친구가 한 명뿐이면 빈 책상에 바로 앉아도 된다.

하지만 연구자가 많고 컴퓨터와 GPU가 적으면 문제가 생긴다.

- 한 사람이 GPU를 전부 사용한다.
- 중요한 작업이 계속 밀린다.
- 누가 무엇을 실행했는지 모른다.
- 실패한 결과를 찾을 수 없다.
- 다른 팀의 작업을 잘못 건드린다.

그래서 이 프로젝트는 규칙을 둔다.

- Tenant: 어느 팀인지 정한다.
- Namespace: 팀별 교실을 나눈다.
- Quota: 한 팀이 쓸 수 있는 양을 정한다.
- Queue: 차례를 정한다.
- Priority: 더 먼저 처리할 필요가 있는지 표시한다.
- RBAC: 누가 무엇을 해도 되는지 정한다.

이 프로젝트에서는 ETRI 하나만 실제 제품 범위다. 그래서 모든 사용자 작업은 tenant-etri 안으로 고정된다.

---

## 6. 사람 대신 로봇도 실험을 부탁할 수 있나요?

가능하다. 그 역할이 MCP Agent Runtime이다.

MCP는 도우미 로봇이 사용할 수 있는 정해진 버튼 모음과 비슷하다.

로봇이 할 수 있는 일:

- 사용할 수 있는 자원 보기
- Science Job 제출하기
- 자기 Job 상태 보기
- Metric 보기
- 실험 Run 목록 보기
- 자기 Job 취소하기

로봇이 할 수 없는 일:

- Kubernetes 관리자 되기
- 다른 Namespace에 마음대로 Job 만들기
- Secret 읽기
- 임의의 위험한 Pod 설정 넣기
- 다른 Tenant의 Job 취소하기

MCP 로봇은 Kubernetes를 직접 만지지 않는다. 사람과 마찬가지로 Science Job API 접수창구를 지나간다.

또한 이 로봇은 혼자 생각해서 계속 일을 벌이는 자율 관리자도 아니다. 누군가 도구를 명시적으로 호출했을 때 정해진 범위만 수행한다.

---

## 7. 화면은 각각 무엇을 보여주나요?

### Research Hub

건물 입구의 안내판이다.

연구 포털, 설명 문서, Kubeflow 같은 내부 화면으로 이동하는 바로가기를 제공한다.

### Science Workspace

연구자가 가장 자주 쓰는 화면이다.

- 자원 상태 보기
- Job 목록 보기
- CPU/GPU Job 제출
- Queue 상태 보기
- Metric과 Artifact 보기
- 자기 Job 취소

### Kubeflow Pipelines UI

실험 공책을 자세히 보는 관리자용 화면이다.

- Run 목록
- 실행 단계
- 성공과 실패
- Parameter
- Metric
- Artifact 연결

현재 별도의 사용자 로그인 화면이 없으므로 내부망에서만 사용해야 한다.

### Grafana

놀이터 전체의 건강 상황판이다.

컴퓨터, API, GPU와 시스템 상태를 그래프로 보는 데 사용한다. 다만 이 프로젝트의 Grafana Dashboard는 저장소에 파일이 있지만 UI Import까지 완전히 검증된 상태는 아니다.

---

## 8. 이 프로젝트가 지키려는 안전 규칙

### 규칙 1. 연구자는 Kubernetes를 직접 만지지 않는다

화면, API 또는 MCP를 통해서만 부탁한다.

### 규칙 2. ETRI 교실 밖으로 나가지 않는다

Namespace, ServiceAccount와 Queue는 서버가 tenant-etri로 고정한다.

### 규칙 3. 위험한 실행 설정을 받지 않는다

관리자 권한, Host 경로 접근, 허락되지 않은 Registry 같은 요청은 거절한다.

### 규칙 4. 실행 상자에 최소 권한만 준다

Job은 일반 사용자 권한으로 실행되고, root 파일 시스템은 읽기 전용이며, 불필요한 Linux Capability를 제거한다.

### 규칙 5. 비밀값을 코드에 넣지 않는다

Token과 Password는 Kubernetes Secret에 보관한다. 화면 JavaScript나 Git 파일에 넣지 않는다.

### 규칙 6. 실패를 성공이라고 부르지 않는다

실제로 확인하지 못한 NetworkPolicy, Grafana Import, Argo CD Sync 같은 항목은 BLOCKED, PARTIAL 또는 미검증으로 표시한다.

---

## 9. 지금 실제로 되는 것은 무엇인가요?

현재 0.3.1에서 실제로 가능한 범위:

- ETRI 내부망에서 Science Workspace 열기
- CPU Science Job 제출·조회·취소
- GPU Science Job 제출과 HAMi 논리 할당
- Kueue를 통한 Quota와 대기 관리
- Kubeflow Run·Metric·Artifact 기록
- MinIO에 Artifact 보관
- MCP를 통한 자원 조회와 자기 Job 관리
- Resource Catalog에서 Node와 GPU 정보 조회
- API와 MCP를 각각 두 개씩 실행해 한 Pod가 멈춰도 서비스 유지
- 내부망 Ingress와 기본 Security Header·Rate Limit 적용

이것은 단순 화면 모형이 아니다. 현재 내부 Kubernetes 클러스터에서 실제 서비스가 실행 중인 MVP다.

---

## 10. 아직 안 되는 것은 무엇인가요?

아직 완성됐다고 말하면 안 되는 범위:

- 여러 기관을 실제로 연결하는 Federation
- 실제 SLURM 작업 제출
- AWS·Azure·GCP 같은 Cloud Site 실행
- 개인별 OIDC 로그인
- HTTPS/TLS 외부 서비스
- 사용자별 완전한 감사 추적
- Flannel 환경에서 NetworkPolicy가 실제 패킷을 막는다는 증명
- 게시 Git 저장소를 이용한 프로젝트 전체 Argo CD 동기화
- 원격 지역으로 백업하고 복구하는 Disaster Recovery
- HAMi가 GPU 성능을 완벽하게 격리한다는 보장

즉, 지금은 “전 세계 누구나 쓰는 완성 서비스”가 아니다.

정확히는:

> ETRI 내부 한 클러스터에서 연구 실험을 안전하고 편리하게 실행해 보는 운영 가능한 MVP다.

---

## 11. 이 프로젝트에서 가장 중요한 세 가지

### 첫째, 어려운 Kubernetes 대신 쉬운 접수창구

연구자는 PodSpec을 직접 만들지 않고 Science Job을 부탁한다.

### 둘째, 실행만 하지 않고 처음부터 끝까지 기록

누가 무엇을 실행했고 어떤 Metric과 Artifact가 나왔는지 Kubeflow가 이어서 기록한다.

### 셋째, 비싼 자원을 차례와 규칙에 따라 공유

Kueue가 차례를 정하고 Scheduler와 HAMi가 CPU·GPU 자리를 배정한다.

---

## 12. 자주 나오는 어려운 말을 쉬운 말로

| 어려운 말 | 쉬운 뜻 |
|---|---|
| Cluster | 여러 컴퓨터를 한 팀처럼 묶은 것 |
| Node | Cluster 안의 컴퓨터 한 대 |
| Kubernetes | 여러 컴퓨터와 프로그램을 관리하는 선생님 |
| Pod | 프로그램 상자를 실제로 여는 작은 실행 공간 |
| Job | 끝이 있는 한 번의 작업 |
| Container Image | 프로그램과 준비물을 담은 밀봉 상자 |
| Namespace | 팀별로 나눈 교실 |
| Tenant | 이 공간을 사용하는 팀 또는 조직 |
| API | 정해진 방식으로 부탁하는 접수창구 |
| MCP | Agent가 사용할 수 있는 정해진 도구 규칙 |
| Pipeline | 실험이 진행되는 순서 |
| Run | Pipeline을 한 번 실제로 실행한 기록 |
| Queue | 자기 차례를 기다리는 줄 |
| Quota | 사용할 수 있는 자원의 최대 양 |
| Scheduler | 어느 컴퓨터에서 실행할지 정하는 역할 |
| CPU | 여러 종류의 일반 계산을 하는 장치 |
| GPU | 같은 종류의 계산을 많이 동시에 하는 장치 |
| Metric | 정확도처럼 숫자로 보는 결과 |
| Artifact | 모델이나 그래프처럼 파일로 남는 결과 |
| Registry | Container Image를 보관하는 창고 |
| MinIO | 결과 파일을 보관하는 객체 저장소 |
| Metadata | 결과를 찾을 수 있게 붙이는 설명과 색인 |
| RBAC | 누가 무엇을 할 수 있는지 정한 권한표 |
| Ingress | 밖에서 내부 서비스로 들어오는 정문 |
| TLS | 통신 내용을 암호화하는 보호 포장 |
| OIDC | 개인별 신원을 확인하는 로그인 방식 |
| MVP | 가장 중요한 기능을 실제로 써 볼 수 있게 만든 첫 제품 |

---

## 13. 비유를 벗기고 정확하게 한 번 더

mini-science-ai-os 0.3.1은 tenant-etri Namespace를 실행 경계로 사용하는 단일 클러스터 내부 연구 플랫폼이다.

사용자는 Portal, REST API 또는 MCP Tool을 통해 Science Job을 제출한다. Science Job API가 입력, Registry, 자원 상한과 Tenant Scope를 검증한다. Kubeflow Pipelines가 Run, Parameter, Metric과 Artifact 흐름을 관리하고, Kueue가 Quota와 Admission을 담당한다. Kubernetes Scheduler와 HAMi가 실제 Node와 논리 GPU 자원을 배정한다. MinIO와 MySQL·Metadata가 결과와 색인을 보관한다.

연구자와 MCP Agent에는 Kubernetes 관리자 권한이나 임의 PodSpec 제출 기능을 제공하지 않는다.

현재 실제 Federation, SLURM·Cloud Adapter, 중앙 SSO, TLS 외부 운영은 범위 밖이다.

---

## 마지막 한 문장

> Science AI OS는 연구자가 “이 실험 해 줘”라고 안전하게 부탁하면, 컴퓨터들이 차례를 정해 실행하고 결과까지 잊지 않도록 보관해 주는 ETRI 내부 연구 놀이터다.

직접 하나씩 실행해 보고 싶다면 [GUIDEBOOK.md](GUIDEBOOK.md)로 이어서 진행한다.

더 기술적인 구조는 [docs/architecture.md](docs/architecture.md), 권한 규칙은 [documentation/permissions.md](documentation/permissions.md), 현재 검증 결과는 [docs/evidence/verification-matrix.md](docs/evidence/verification-matrix.md)를 참고한다.
