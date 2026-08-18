# MLflow + Grafana 실증 증거

검증 시각: 2026-08-14 19:01 KST

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

## 브라우저 증거

- [MLflow Runs](evidence/mlflow-runs.png)
- [MLflow Model Registry](evidence/mlflow-model-registry.png)
- [Grafana MLflow/GPU Dashboard](evidence/grafana-mlflow-gpu-dashboard.png)

Playwright로 두 웹 UI에 접속해 DOM snapshot과 viewport를 확인했다. Grafana
Dashboard API, MLflow REST API, Prometheus query도 별도로 조회해 화면 값과 원본
데이터가 일치함을 확인했다.

## 주장 경계

이번 증거는 MLflow의 experiment/run, parameter/metric/artifact, model version/alias와
Grafana의 Prometheus/DCGM 조회가 실제 동작함을 증명한다. MLflow는 SQLite와
`local-path` PVC를 사용하는 단일 인스턴스이므로 고가용성, 외부 저장소, 원격 DR,
장기 운영 성능은 증명하지 않는다.
