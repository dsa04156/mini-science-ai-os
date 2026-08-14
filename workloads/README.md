# Demo workloads

- `cpu-demo/job.yaml`: Kueue CPU Job Manifest 검증용.
- `gpu-demo/job.yaml`: 실제 조사된 HAMi Resource를 쓰는 소형 GPU Job.
- `kubeflow-demo/request.json`: Kubernetes Manifest 대신 Science Job API로 KFP Run을 제출하는 권장 Demo.

```bash
make demo
make destroy-demo
```

직접 Job YAML을 적용하는 두 Manifest는 Scheduler/Queue 진단용이다. 최종 사용자 경로는 `kubeflow-demo/request.json`을 Tenant Science API에 POST하는 방식이다.
