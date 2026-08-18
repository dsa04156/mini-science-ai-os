# 7분 라이브 데모 동선

라이브 데모는 새 인프라를 설치하지 않는다. 이미 배포된 제품의 상태와 보존된
증거를 먼저 보여주고, 변경이 필요한 훈련은 계획 출력까지만 수행한다.

## 사전 점검

```bash
make status
make portfolio-check
```

두 명령 중 하나라도 실패하면 라이브 변경을 하지 않고 저장된 Evidence로 전환한다.

## 진행 순서

### 0:00-1:00 — 실제 장비 운영 화면과 제품 경계

먼저 Science Workspace `개요`에서 5/5 Node, 2/2 Physical GPU, 6/6 Platform,
Kueue Ready를 보여준다. 값이 실제 Kubernetes·Prometheus·DCGM에서 수집되므로
수치가 변할 수 있다는 점을 먼저 말하고, `토폴로지`에서 같은 장비와 Workload
배치를 교차 확인한다.

```bash
sed -n '1,90p' docs/architecture.md
kubectl get deploy,pdb -n tenant-etri
```

설명: 연구자와 Agent는 Kubernetes API 대신 Science API를 사용한다. API와 MCP는
각각 2 Replica이며, 종속 데이터 계층의 한계는 별도로 공개한다.

### 1:00-2:30 — GPU와 Queue

```bash
kubectl get localqueue -n tenant-etri
kubectl get workloads.kueue.x-k8s.io -n tenant-etri
kubectl get nodes -L accelerator,gpu.platform
```

성공했던 실제 할당은 `docs/evidence/verification-matrix.md`와 가장 최근
`docs/evidence/demo-*.md`에서 보여준다. 데모 중 새 GPU Job은 자원 경합을 유발할 수
있으므로 필요할 때만 `make demo`를 실행한다.

### 2:30-4:15 — MLOps 실행 이력과 모델 레지스트리

```bash
kubectl get deploy -n kubeflow ml-pipeline metadata-grpc-deployment mysql
kubectl get deploy,job,pod,pvc -n science-ai-mlops
kubectl logs -n science-ai-mlops job/mlflow-functional-demo
```

Kubeflow Pipelines의 `NAIS integration demos`에서 `nais-kfp-mlflow-integration`
Run이 성공했고 component 입력에 `mae=0.09`, threshold `0.1`, MLflow tracking URI가
표시되는 것을 먼저 보여준다. 이어 MLflow `Model training → Runs`의
`kubeflow-train-register` Run에서 parameter, metric, artifact를 확인하고 Model Registry의
`nais-kfp-mean-baseline` v1과 `candidate` alias를 연결한다. 이 구성은 기능 실증용
SQLite/PVC 단일 인스턴스이며 고가용성 주장은 하지 않는다.

### 4:15-5:15 — Grafana 실제 관측값

Grafana의 `NAIS Functional Demo — Kubeflow, MLflow & GPU Operations` Dashboard에서 다음을
한 화면으로 보여준다.

- MLflow tracking server, Functional run, MinIO가 각각 `1`
- Ready cluster nodes가 `5`
- RTX 5060 Ti/5080의 DCGM GPU 사용률과 framebuffer 사용량
- KFP → MLflow 성공 `1`과 실제 component 실행시간
- Kueue pending workload와 Kubeflow Pipelines UI 상태

### 5:15-6:15 — Agent 권한 경계

```bash
kubectl auth can-i get secrets \
  --as=system:serviceaccount:tenant-etri:agent-runtime -n tenant-etri
kubectl auth can-i create jobs \
  --as=system:serviceaccount:tenant-etri:agent-runtime -n tenant-etri
```

기대 결과는 모두 `no`다. 그 다음 `docs/permissions.md`와 Audit Evidence를 보여준다.

### 6:15-7:00 — 실패를 숨기지 않는 운영

```bash
bash portfolio/scripts/recovery-drill.sh plan
bash portfolio/scripts/resilience-drill.sh plan
```

격리 복구와 API Pod 교체 훈련의 단계, 안전장치, 성공 조건을 보여준 뒤
`portfolio/nais-technical-1-matrix.md`의 GAP으로 마무리한다.

## 실패 시 전환 순서

1. 라이브 명령 재시도는 한 번만 한다.
2. 그 이후에는 `docs/evidence/verification-matrix.md`로 전환한다.
3. 실패 원인과 확인할 다음 명령을 말한다. 화면을 숨기거나 PASS로 표현하지 않는다.
4. Secret 값, Token, 내부 Credential은 화면에 출력하지 않는다.
