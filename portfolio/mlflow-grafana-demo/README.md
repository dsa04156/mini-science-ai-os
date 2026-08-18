# Kubeflow Pipelines + MLflow + Grafana 기능 실증

이 구성은 고가용성보다 실제 기능 동작을 빠르게 보여주기 위한 단일 인스턴스 PoC다.
MLflow 3.13.0 한 개와 SQLite/PVC를 사용하며, 데모 Job이 experiment, run, parameter,
metric, artifact, registered model version과 `champion` alias를 만든다. Grafana dashboard는
기존 Prometheus와 DCGM datasource를 그대로 사용한다.

추가 KFP Pipeline은 CPU component에서 MLflow Run과 artifact를 기록한다. `mae`가
`registration_threshold` 이하일 때만 `nais-kfp-mean-baseline` 모델 버전과 `candidate`
alias를 생성한다. KFP와 MLflow 사이에는 TCP 5000만 허용하는 양방향 NetworkPolicy를
추가한다.

## 배포와 확인

```bash
kubectl apply -k portfolio/mlflow-grafana-demo
kubectl rollout status deployment/mlflow -n science-ai-mlops --timeout=10m
kubectl wait -n science-ai-mlops --for=condition=complete job/mlflow-functional-demo --timeout=10m
kubectl logs -n science-ai-mlops job/mlflow-functional-demo
```

KFP API를 로컬로 전달한 터미널을 하나 유지한다.

```bash
kubectl -n kubeflow port-forward svc/ml-pipeline 18888:8888
```

다른 터미널에서 Pipeline을 컴파일하고 실제 Run을 제출한다.

```bash
uv run --isolated --with-requirements requirements.txt -- \
  python portfolio/mlflow-grafana-demo/kfp_mlflow_pipeline.py submit \
  --package /tmp/nais-kfp-mlflow-integration.yaml
```

- MLflow: <http://mlflow.192.168.0.56.nip.io>
- Kubeflow Pipelines: <http://kubeflow-pipelines.192.168.0.56.nip.io>
- Grafana dashboard: <http://grafana.192.168.0.56.sslip.io/d/nais-mlflow-functional-demo>
- 검증 기록과 화면: [evidence.md](evidence.md)

데모 Job을 다시 실행할 때만 프로젝트 소유 Job을 지운 뒤 재적용한다.

```bash
kubectl delete job mlflow-functional-demo -n science-ai-mlops
kubectl apply -k portfolio/mlflow-grafana-demo
```

## 의도한 제한

- MLflow replica는 1개이고 SQLite/local-path PVC를 사용한다.
- 인증은 별도 구성하지 않았으며 Traefik 내부망 allowlist로 접근 범위를 제한한다.
- 고가용성, 외부 PostgreSQL/object storage, 원격 백업·DR은 운영 전환 항목이다.
- KFP 통합 component는 기능 증명용 mean-baseline이며 실제 학습 성능을 주장하지 않는다.
- 기존 Prometheus, Grafana, DCGM, MinIO 배포 자체는 변경하지 않는다.
