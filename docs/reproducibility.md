# Reproducibility

## 재현 식별자

각 Science Job과 KFP Run에는 Tenant, Project, Git Commit, Container Image, Dataset Version, Experiment, Parameter, Metric, Node, Accelerator, 시작/종료·성공/실패 상태가 연결된다. API는 동일 요청을 재제출할 수 있지만 새 `jobId`와 `kubeflowRunId`가 생성된다.

현재 Demo 고정값:

- 기본 Image: `192.168.0.56:5000/mini-science-ai-os:0.3.1`
- 검증 Digest: `sha256:f2a36e42338a9bbfa3fd9d627aa33ace2fcf2f63add7e1c7465b9590acfd61b5`
- Dataset Version: `factory-v1`
- CPU command: `python -m science_os.demo --mode cpu`
- GPU command: `python -m science_os.demo --mode gpu`
- Artifact root: `s3://kubeflow-pipelines/v2/artifacts`

운영에서는 `REQUIRE_IMAGE_DIGEST=true`로 전환하고 요청 Image를 Digest로 고정해야 한다. `gitCommit=unknown`이나 Dataset Version이 없는 실행은 재현 완료로 분류하지 않는다.

## CPU 재실행

```bash
export SCIENCE_TOKEN="$(kubectl get secret tenant-api-token -n tenant-etri -o jsonpath='{.data.token}' | base64 -d)"
kubectl -n tenant-etri port-forward svc/science-job-api 18080:8000
curl -sS -X POST http://127.0.0.1:18080/v1/jobs \
  -H "X-Science-Token: ${SCIENCE_TOKEN}" \
  -H 'Content-Type: application/json' \
  --data @workloads/kubeflow-demo/request.json
```

완료 후 `/status`, `/metrics`, `/artifacts` 응답과 KFP Run ID를 함께 기록한다. 검증된 CPU Run 예시는 `737e4776-2f36-40c8-a665-e0675ff30e13`이다.

## GPU 재실행

GPU 요청은 Phase 0에서 확인한 실제 HAMi Resource `nvidia.com/gpu`, `nvidia.com/gpumem`, `nvidia.com/gpucores`를 사용한다. 검증된 두 Run은 같은 GPU UUID에 각각 1024MiB/10% 논리 할당되었다. 이는 재현 가능한 할당 요청이지 성능 격리 보장이 아니다.

## Artifact와 보존 한계

KFP Metadata/Run DB는 `kubeflow` Namespace MySQL PVC, Artifact는 `science-ai-mlops` MinIO PVC에 저장된다. 둘 다 발견된 `local-path` StorageClass를 사용하므로 Node 장애를 견디는 원격 백업이 아니다. 운영 전 외부 DB Backup과 Versioned Object Storage를 구성해야 한다.
