# Science AI OS 직접 실습 가이드북

이 문서는 mini-science-ai-os 0.3.1을 처음 보는 사용자가 현재 운영 중인 ETRI 내부 환경을 하나씩 확인하는 순서다. 앞 단계의 체크포인트를 확인한 뒤 다음 단계로 넘어간다.

프로젝트가 무엇인지부터 쉽게 이해하고 싶다면 [EASY_EXPLAINER.md](EASY_EXPLAINER.md)를 먼저 읽는다.

현재 제품 경계는 단일 Kubernetes 클러스터와 tenant-etri다. 외부 공개 서비스가 아니며, 실제 SLURM·Cloud·다기관 Federation은 아직 실습 대상이 아니다.

## 먼저 알아둘 안전 규칙

- 웹에서 개념과 전체 구조를 먼저 읽으려면 `http://mini-science-ai-os.192.168.0.56.nip.io/`를 연다.
- 1장부터 8장까지는 조회 또는 제한된 데모 작업이다.
- 현재 제품은 TLS와 개인별 로그인이 없는 trusted-network 모드다. 승인된 내부망에서만 사용한다.
- Secret 값을 화면에 출력하거나 문서에 붙여 넣지 않는다.
- 일반 점검 중 PVC, Namespace, Secret을 삭제하지 않는다.
- make bootstrap, make productize, make etri-only, make rollback은 초급 실습 명령이 아니다.
- GPU Memory/Core 값은 논리 할당량이다. 실제 GPU 성능 격리를 의미하지 않는다.
- 예전 nais.* 허브 주소는 현재 HTTP 404다. 현재 허브는 research-hub.*와 kubeedge-hub.*로 나뉘어 있다.

## 전체 실습 지도

| 단계 | 해보는 것 | 변경 여부 | 성공 기준 |
|---|---|---:|---|
| 1 | 접속 환경과 클러스터 확인 | 없음 | kubectl 응답 |
| 2 | 제품 상태 확인 | 없음 | INTERNAL_PRODUCT=READY |
| 3 | 연구 포털 둘러보기 | 세션 Cookie | 개요 화면 표시 |
| 4 | CPU Science Job 제출 | Job/Run 생성 | Succeeded와 Metric |
| 5 | Kubeflow 실행 이력 확인 | 없음 | 같은 Run 확인 |
| 6 | GPU Science Job 제출 | Job/Run 생성 | HAMi 할당과 완료 |
| 7 | Queue와 자원 상태 확인 | 없음 | Kueue/Pod 상태 확인 |
| 8 | MCP 도구 호출 | 조회, 선택적 Job 생성 | Tool 결과와 Audit |
| 9 | 직접 API 호출 | 조회 | HTTP 200과 Job 목록 |
| 10 | 로컬 소스 검증 | 임시 디렉터리만 | 17 passed |
| 11 | 모니터링과 장애 위치 확인 | 없음 | 구성요소 Ready |
| 12 | 데모 정리 | 데모 Job 삭제 | 데모 리소스 부재 |

---

## 1장. 접속 환경 확인

### 1-1. 프로젝트 위치로 이동

    cd /home/jinuk/codex-work/platform
    pwd

기대 결과:

    /home/jinuk/codex-work/platform

### 1-2. Kubernetes 연결 확인

    kubectl config current-context
    kubectl cluster-info
    kubectl get nodes

체크포인트:

- current-context가 의도한 실습 클러스터여야 한다.
- Kubernetes control plane 조회가 성공해야 한다.
- Node 목록에 Ready 상태가 보여야 한다.

인증 오류나 connection refused가 나오면 다음 단계로 가지 않는다. kubeconfig와 VPN/내부망 연결부터 확인한다.

---

## 2장. 제품이 살아 있는지 확인

### 2-1. 준비된 상태 명령 실행

    make status

마지막 부분에서 다음 값을 확인한다.

    KIST_NAMESPACE=absent
    PRODUCT_HTTP=200
    INTERNAL_PRODUCT=READY

readyz 응답에는 tenant=etri, namespace=tenant-etri, version=0.3.1, profile=internal-production, accessMode=trusted-network가 있어야 한다.

### 2-2. 핵심 Pod 확인

    kubectl get deploy,pod,svc,ingress,pdb -n tenant-etri

체크포인트:

- science-job-api Deployment가 2/2 Ready
- agent-runtime Deployment가 2/2 Ready
- Pod가 Running
- science-workspace Ingress 존재
- 두 PDB가 표시됨

---

## 3장. 웹 화면 둘러보기

### 3-1. 연구 서비스 허브

LAN:

    http://research-hub.192.168.0.56.nip.io/

기관 라우팅:

    http://research-hub.10.254.192.217.nip.io/

두 주소 중 현재 네트워크에서 열리는 하나를 사용한다. 이 문서 작성 시점에는 둘 다 HTTP 200으로 확인됐다.

### 3-2. Science Workspace

LAN:

    http://science-workspace.192.168.0.56.nip.io/portal/

기관 라우팅:

    http://science-workspace.10.254.192.217.nip.io/portal/

접근 키 입력 화면은 없다. 내부망 요청이면 ETRI 고정 HttpOnly 세션이 자동으로 만들어진다.

개요에서 전체 작업, 실행 중, 대기 중, GPU Node 수, 최근 작업과 ETRI Tenant 고정을 확인한다.

### 3-3. 제품 설명 페이지

LAN:

    http://mini-science-ai-os.192.168.0.56.nip.io/

기관 라우팅:

    http://mini-science-ai-os.10.254.192.217.nip.io/

설명 페이지는 구성요소와 사용자 흐름을 보여준다. 실제 작업은 Science Workspace에서 수행한다.

---

## 4장. 첫 CPU Science Job 제출

Science Workspace 왼쪽 메뉴에서 새 작업을 선택한다.

### 4-1. 실험 정보

| 필드 | 입력값 |
|---|---|
| 프로젝트 | physical-ai |
| 실험 이름 | my-first-cpu |
| 데이터셋 버전 | factory-v1 |
| Git Commit | manual-guide |

### 4-2. 실행 환경

화면이 자동으로 채운 기본 이미지를 그대로 사용한다. 현재 기준 이미지는 다음 버전이다.

    192.168.0.56:5000/mini-science-ai-os:0.3.1

Command는 한 줄에 인자 하나씩 입력한다.

    python
    -m
    science_os.demo
    --mode
    cpu

### 4-3. 자원

| 필드 | 입력값 |
|---|---|
| CPU | 500m |
| Memory | 512Mi |
| 우선순위 | 보통 |
| GPU 사용 | 끔 |

검증 후 제출을 누른다.

### 4-4. 결과

작업 메뉴에서 방금 만든 Job을 연다. 작업이 짧아서 Pending과 Running을 지나 바로 Succeeded가 될 수 있다.

확인할 항목:

- Science Job ID와 Kubeflow Run ID
- Kueue Admission 및 Pipeline 상태
- Parameter의 mode=cpu
- Metric의 loss 약 0.125
- Metric의 accuracy 약 0.875
- Artifact 또는 실행 결과

실패했을 때:

    kubectl get jobs,pods,workloads -n tenant-etri
    kubectl describe workload -n tenant-etri WORKLOAD_NAME
    kubectl logs -n tenant-etri JOB_POD_NAME

WORKLOAD_NAME과 JOB_POD_NAME은 바로 앞 조회 결과에서 복사한다.

---

## 5장. Kubeflow에서 같은 실행 확인

Kubeflow Pipelines UI:

LAN:

    http://kubeflow-pipelines.192.168.0.56.nip.io/

기관 라우팅:

    http://kubeflow-pipelines.10.254.192.217.nip.io/

Runs 화면에서 4장에서 받은 Kubeflow Run ID 또는 my-first-cpu를 찾는다.

체크포인트:

- Run 상태가 Succeeded
- 실행 Graph 표시
- Input/Output Parameter 확인
- Science Workspace에서 본 Metric/Artifact와 연결

현재 Kubeflow UI에는 사용자 인증이 없다. 내부망 운영 보조 화면으로만 사용한다.

---

## 6장. GPU Science Job 제출

Science Workspace의 새 작업으로 돌아간다.

| 필드 | 입력값 |
|---|---|
| 프로젝트 | physical-ai |
| 실험 이름 | my-first-gpu |
| 데이터셋 버전 | factory-v1 |
| Git Commit | manual-guide |
| CPU | 500m |
| Memory | 512Mi |
| 우선순위 | 보통 |
| GPU 사용 | 켬 |
| GPU 개수 | 1 |
| GPU Memory MiB | 1024 |
| GPU Core % | 10 |

Command:

    python
    -m
    science_os.demo
    --mode
    gpu

검증 후 제출한다. 기대 Metric은 loss 약 0.095, accuracy 약 0.905다.

HAMi 논리 할당 확인:

    kubectl get pods -n tenant-etri -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.metadata.annotations.hami\.io/vgpu-devices-allocated}{"\n"}{end}'

Annotation이 비어 있으면:

    kubectl get jobs,pods,workloads -n tenant-etri
    kubectl describe pod -n tenant-etri GPU_POD_NAME

GPU 1024MiB/10%는 할당 정책 값이지 처리량 보장이 아니다.

---

## 7장. Queue와 자원 상태 이해하기

### 7-1. Kueue 상태

    kubectl get localqueue -n tenant-etri tenant-etri
    kubectl get clusterqueue science-shared
    kubectl get workloads -n tenant-etri

읽는 방법:

- Pending Workloads: Quota 또는 자원을 기다리는 작업 수
- Admitted Workloads: Queue가 실행을 허용한 작업 수
- Workload의 Admitted Condition: 입장 여부

### 7-2. 자원 카탈로그

포털 개요의 GPU Node와 Ready Node 수를 확인한다. CLI에서는 다음을 확인한다.

    kubectl get deploy,pod,svc -n science-ai-system
    kubectl logs -n science-ai-system deploy/resource-catalog --tail=50

Quota 대기를 만들기 위해 큰 작업을 여러 개 제출하지 않는다. 이는 별도 부하 실습 창에서 수행한다.

---

## 8장. MCP Agent 도구 확인

MCP Runtime은 Kubernetes를 직접 조작하지 않고 Science Job API만 호출한다.

### 8-1. 안전한 조회 호출

    kubectl exec -n tenant-etri deploy/agent-runtime -- python -c 'import asyncio; from science_os.mcp_server import list_available_resources; print(asyncio.run(list_available_resources()))'

Python 예외 없이 Site/Node/CPU/GPU 정보를 담은 결과가 나와야 한다.

제공 도구:

- list_available_resources
- submit_science_job
- get_job_status
- get_run_metrics
- list_experiment_runs
- cancel_own_job

### 8-2. 선택 실습: MCP로 제출 후 취소

아래 명령은 실제 Job과 KFP Run을 만든 뒤 취소한다.

    kubectl exec -i -n tenant-etri deploy/agent-runtime -- python - <<'PY'
    import asyncio
    import json
    from science_os.mcp_server import cancel_own_job, get_job_status, submit_science_job

    async def main():
        submitted = await submit_science_job({
            "project": "manual-mcp",
            "image": "192.168.0.56:5000/mini-science-ai-os:0.3.1",
            "command": ["python", "-m", "science_os.demo", "--mode", "cpu"],
            "resources": {"cpu": "100m", "memory": "128Mi"},
            "datasetVersion": "manual-v1",
            "experiment": "submit-and-cancel",
            "priority": "normal"
        })
        job_id = submitted["jobId"]
        status = await get_job_status(job_id)
        cancelled = await cancel_own_job(job_id)
        print(json.dumps({"jobId": job_id, "status": status, "cancelled": cancelled}, sort_keys=True))

    asyncio.run(main())
    PY

Audit 확인:

    kubectl logs -n tenant-etri deploy/agent-runtime --tail=100

Tool, Tenant, 권한 결정과 연결된 Job ID가 보여야 한다. Token 값은 마스킹돼야 한다.

---

## 9장. 직접 Science Job API 사용

이 단계는 터미널 환경변수에 API Token을 잠시 보관한다. Token을 출력하거나 화면 공유하지 않는다.

첫 번째 터미널:

    kubectl -n tenant-etri port-forward svc/science-job-api 18080:8000

두 번째 터미널:

    export SCIENCE_TOKEN="$(kubectl get secret tenant-api-token -n tenant-etri -o jsonpath='{.data.token}' | base64 -d)"
    curl -sS -H "X-Science-Token: $SCIENCE_TOKEN" http://127.0.0.1:18080/v1/jobs

ETRI Job 목록 JSON이 나와야 한다.

추가 조회:

    curl -sS http://127.0.0.1:18080/readyz
    curl -sS -H "X-Science-Token: $SCIENCE_TOKEN" http://127.0.0.1:18080/v1/config
    curl -sS -H "X-Science-Token: $SCIENCE_TOKEN" http://127.0.0.1:18080/v1/resources/summary

종료:

    unset SCIENCE_TOKEN

첫 번째 터미널의 Port Forward는 Ctrl+C로 종료한다.

---

## 10장. 로컬 소스와 테스트 검증

현재 체크아웃은 일부 디렉터리가 root 소유이고 기본 Python에 pytest가 없어 make validate가 바로 실패할 수 있다. 코드 결함과 환경 문제를 분리하기 위해 임시 가상환경을 사용한다.

    cd /home/jinuk/codex-work/platform
    TMP_PLATFORM_TEST="$(mktemp -d)"
    python3 -m venv "$TMP_PLATFORM_TEST/venv"
    "$TMP_PLATFORM_TEST/venv/bin/python" -m pip install -r requirements-dev.txt
    PYTHONPYCACHEPREFIX="$TMP_PLATFORM_TEST/pycache" "$TMP_PLATFORM_TEST/venv/bin/python" -m compileall -q services
    PYTHONPYCACHEPREFIX="$TMP_PLATFORM_TEST/pycache" "$TMP_PLATFORM_TEST/venv/bin/python" -m pytest -q -p no:cacheprovider tests

현재 기대 결과:

    17 passed

이 방법은 프로젝트 디렉터리에 pycache나 pytest cache를 쓰지 않는다.

관리자가 이 복사본 전체를 현재 사용자 소유로 바꿔도 된다고 확인한 경우에만 다음을 실행한다.

    sudo chown -R "$(id -un):$(id -gn)" /home/jinuk/codex-work/platform
    make validate

공유 볼륨이나 다른 운영 사용자가 쓰는 복사본에서는 소유권을 바꾸지 않는다.

---

## 11장. 운영 구성요소 확인

### 11-1. Kubeflow

    kubectl get deploy -n kubeflow ml-pipeline ml-pipeline-ui metadata-grpc-deployment mysql
    kubectl get --raw '/api/v1/namespaces/kubeflow/services/http:ml-pipeline:8888/proxy/apis/v2beta1/healthz'

KFP Health 응답의 tag_name은 2.17.0이어야 한다.

### 11-2. Artifact 저장소

    kubectl get sts,pod,svc,pvc -n science-ai-mlops

체크포인트:

- minio StatefulSet 1/1 Ready
- minio-0 Running
- data-minio-0 PVC Bound

### 11-3. Alert와 모니터링

    kubectl get prometheusrule -n science-ai-system mini-science-ai-os-alerts
    kubectl get servicemonitor -A -l science-ai.io/managed-by=mini-science-ai-os

Grafana Dashboard JSON은 monitoring/grafana/science-ai-overview.json에 있다. 현재는 Rule 적용 완료, Grafana UI Import 미검증 상태다.

---

## 12장. 데모 정리

완료된 Job은 포털에서 확인한다. 실행 중인 작업만 취소가 필요하며, 이미 Succeeded인 작업을 억지로 삭제할 필요는 없다.

프로젝트 데모 정리 전 대상 확인:

    kubectl get jobs -A -l science-ai.io/demo=true

목록이 본인이 정리하려는 데모인지 확인한 뒤:

    make destroy-demo

실행 후:

    kubectl get jobs -A -l science-ai.io/demo=true

make destroy-demo는 프로젝트 데모 Job을 정리하고 운영 PVC와 플랫폼 구성요소는 보존하도록 설계돼 있다.

---

## 완료 체크리스트

- [ ] make status에서 INTERNAL_PRODUCT=READY를 확인했다.
- [ ] Science Workspace 개요를 열었다.
- [ ] CPU Job을 제출하고 Succeeded와 Metric을 확인했다.
- [ ] 같은 Run을 Kubeflow UI에서 찾았다.
- [ ] GPU Job의 HAMi 논리 할당을 확인했다.
- [ ] Kueue LocalQueue와 ClusterQueue를 조회했다.
- [ ] MCP의 list_available_resources를 호출했다.
- [ ] 직접 API로 Job 목록을 조회했다.
- [ ] 임시 환경에서 테스트 17개가 통과했다.
- [ ] MinIO PVC와 KFP Health를 확인했다.
- [ ] 생성한 데모 리소스를 확인하거나 정리했다.

## 현재 실습으로 검증할 수 없는 범위

- 실제 다기관 Federation
- 실제 SLURM 제출과 Cloud Site 실행
- TLS/OIDC와 개인별 사용자 감사
- Flannel 환경의 NetworkPolicy 강제
- 게시 Git 저장소를 통한 프로젝트 Argo CD Sync
- 원격 Disaster Recovery
- GPU 처리량과 대역폭의 물리적 성능 격리

현재 제품의 정확한 목표는 ETRI 단일 테넌트 내부 Science Workspace다.

## 관련 문서

- [README.md](README.md) — 제품 개요와 주요 명령
- [docs/architecture.md](docs/architecture.md) — 시스템 구조와 책임 분리
- [docs/runbook.md](docs/runbook.md) — 운영 절차
- [docs/evidence/verification-matrix.md](docs/evidence/verification-matrix.md) — 기능별 실제 검증 판정
- [documentation/permissions.md](documentation/permissions.md) — 권한 경계
- [documentation/variables.md](documentation/variables.md) — 설정과 Secret
- [documentation/automation.md](documentation/automation.md) — MCP Agent 도구와 Guardrail
- [documentation/tests.md](documentation/tests.md) — 테스트 커버리지 지도
