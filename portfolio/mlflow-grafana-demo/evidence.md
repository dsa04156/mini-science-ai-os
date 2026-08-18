# Kubeflow Pipelines + MLflow + Grafana 실증 증거

최신 검증 시각: 2026-08-18 14:48 KST

## 실행 결과

- `science-ai-mlops/mlflow` Deployment: `1/1 Available`
- `science-ai-mlops/mlflow-functional-demo` Job: `Complete`
- MLflow experiment: `nais-functional-demo`
- 최신 Run: `e364798f3b0640c4a4ff1394e5535209`, `FINISHED`
- Metrics: `mae=0.125`, `samples=8`
- Registered model: `nais-demo-mean-baseline`, latest `Version 3`, alias `champion`
- Grafana dashboard UID: `nais-mlflow-functional-demo`
- Grafana live values: MLflow `1`, demo Job `1`, MinIO `1`, Ready Nodes `5`
- DCGM series: NVIDIA GeForce RTX 5060 Ti와 RTX 5080가 실제 값으로 렌더링됨

### KFP → MLflow 통합 실행

- KFP experiment: `NAIS integration demos`
- KFP run: `9e23aab6-9b9c-4b52-bdca-079a998b575b`, `SUCCEEDED`
- Workflow: `nais-kfp-mlflow-integration-fvzvq`, `Succeeded`
- CPU component: request `100m`/limit `500m`, memory request `256Mi`/limit `1Gi`
- MLflow experiment: `nais-kfp-mlflow-integration`
- MLflow run: `5e9e2e422403454f9548b146dcc33396`, `FINISHED`
- Parameters: `orchestrator=kubeflow-pipelines`, `dataset_version=synthetic-observations-v2`, threshold `0.1`
- Metrics: `mae=0.09`, `samples=8`
- Artifact: `evidence/kfp-mlflow-summary.json`
- Registered model: `nais-kfp-mean-baseline` version `1`, alias `candidate`, status `READY`
- Grafana live values: KFP → MLflow success `1`, component duration `23s`

## 브라우저 증거

- [MLflow Runs](evidence/mlflow-runs.png)
- [MLflow Model Registry](evidence/mlflow-model-registry.png)
- [Grafana MLflow/GPU Dashboard](evidence/grafana-mlflow-gpu-dashboard.png)
- [Kubeflow Pipeline Run](evidence/kfp-mlflow-run.png)
- [MLflow KFP Run](evidence/mlflow-kfp-run.png)
- [MLflow Candidate Model](evidence/mlflow-kfp-candidate-model.png)
- [Grafana KFP/MLflow/GPU Dashboard](evidence/grafana-kfp-mlflow-dashboard.png)

Playwright로 Kubeflow, MLflow, Grafana 세 웹 UI에 접속해 DOM snapshot과 viewport를
확인했다. KFP API와 Workflow 상태, MLflow REST API, Prometheus query도 별도로
조회해 화면 값과 원본 데이터가 일치함을 확인했다.

## 주장 경계

이번 증거는 KFP CPU component가 MLflow의 experiment/run, parameter/metric/artifact,
model version/alias를 실제 생성하고 Grafana가 그 Pod 상태와 Prometheus/DCGM 값을
조회함을 증명한다. MLflow는 SQLite와 `local-path` PVC를 사용하는 단일 인스턴스이므로
고가용성, 외부 저장소, 원격 DR, 장기 운영 성능은 증명하지 않는다. mean-baseline과
고정된 소규모 metric은 통합 경로 검증용이며 모델 품질 검증 결과가 아니다.
