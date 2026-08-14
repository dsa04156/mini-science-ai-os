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

### 2:30-4:00 — MLOps 이력

```bash
kubectl get deploy -n kubeflow ml-pipeline metadata-grpc-deployment mysql
kubectl get pod,pvc -n science-ai-mlops
```

포털에서 Job 상세의 Kubeflow Run ID, Metric, Artifact URI를 보여준다.

### 4:00-5:15 — Agent 권한 경계

```bash
kubectl auth can-i get secrets \
  --as=system:serviceaccount:tenant-etri:agent-runtime -n tenant-etri
kubectl auth can-i create jobs \
  --as=system:serviceaccount:tenant-etri:agent-runtime -n tenant-etri
```

기대 결과는 모두 `no`다. 그 다음 `docs/permissions.md`와 Audit Evidence를 보여준다.

### 5:15-6:15 — SLURM 확장 PoC

```bash
python3 -m portfolio.slurm_adapter plan \
  --name spectroscopy --script portfolio/examples/train.sh \
  --gpus 2 --cpus 8 --memory-mb 32768
```

실물 Scheduler 호출 없이 생성되는 `sbatch` 인자와 입력 검증을 보여준다. 이 PoC가
현재 제품 실행 경로에 연결되지 않았음을 명확히 말한다.

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
