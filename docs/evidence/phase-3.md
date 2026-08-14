# Phase 3 evidence — Kueue and HAMi GPU path

## 1. Changed files

- `apps/kueue/kustomization.yaml`
- `apps/kueue/queues.yaml`
- `services/science_os/job_api.py`
- `workloads/gpu-demo/job.yaml`
- `scripts/demo.sh`, `scripts/destroy-demo.sh`

## 2. Commands executed

```text
rtk make bootstrap
rtk make demo
rtk kubectl get workload -n tenant-etri -o wide
rtk kubectl get pod -n tenant-etri <gpu-pod> -o jsonpath='{.metadata.annotations}'
rtk kubectl describe pod -n tenant-etri <gpu-pod>
rtk kubectl get --raw '/api/v1/namespaces/kube-system/services/http:prometheus-kube-prometheus-prometheus:9090/proxy/api/v1/query?query=DCGM_FI_DEV_GPU_UTIL'
```

## 3. Actual results

Final `0.1.2` demo (`demo-20260810T091821Z.md`) submitted:

- CPU Job `3c0e05e88e85`: Complete.
- queue-wait Job `bf7d5c3fef79`: admitted and Complete after 67 seconds.
- GPU Jobs `0e8cd04e65e3` and `2a708d7e5416`: both Complete; pod resources included `nvidia.com/gpu=1`, `nvidia.com/gpumem=1024`, `nvidia.com/gpucores=10`.
- low-priority hold `0b8c1eada3fd`: initially `Suspended`; Workload conditions recorded `Preempted`/`Requeued`, then it was admitted after higher-priority work finished.
- HAMi annotations recorded `hami.io/vgpu-node` and GPU UUIDs. `hami-scheduler` Scheduled/BindingSucceed events were observed.
- Discovered names from live HAMi config were used: `nvidia.com/gpu`, `nvidia.com/gpumem`, `nvidia.com/gpucores`; split count was 10.
- DCGM snapshot returned both RTX 5080 and RTX 5060 Ti. The demo Python process did not run CUDA; observed utilization was only a telemetry snapshot, not a performance benchmark.

An earlier run placed two small GPU Jobs on the same `etri-ser0001-cg0msb` physical GPU, proving that a sharing scenario can occur. The final run also legitimately placed them on separate available GPUs. Neither result proves physical QoS isolation.

## 4. Problems and risks

- HAMi logical memory/core limits are not physical performance isolation. A CUDA benchmark and interference/QoS test were not run.
- The current ClusterQueue is intentionally shared by the two tenant LocalQueues; fairness and production quota policy need review.

## 5. Next phase

Resource Catalog and MLOps/API/MCP phases proceeded. A real GPU benchmark is a follow-up, not a prerequisite for the logical allocation path.
