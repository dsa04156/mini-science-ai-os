# Phase 0 evidence — existing environment inventory

조사 시각: 2026-08-10 (Asia/Seoul)

모든 조회는 현재 kube-context `kubernetes-admin@kubernetes`에서 수행했습니다. 기존 리소스에는 변경을 가하지 않았습니다. 출력은 긴 목록을 제외하고 핵심 결과를 그대로 보존했습니다.

## 명령과 핵심 출력

### Kubernetes version

명령:

```bash
kubectl version --output=yaml
```

출력:

```text
clientVersion.gitVersion: v1.31.14
serverVersion.gitVersion: v1.31.14
kustomizeVersion: v5.4.2
```

### Nodes, architecture, taints, allocatable

명령:

```bash
kubectl get nodes -o wide
kubectl get nodes --show-labels
kubectl get nodes -o custom-columns=NAME:.metadata.name,ARCH:.status.nodeInfo.architecture,TAINTS:.spec.taints,ALLOCATABLE:.status.allocatable
```

출력 요약:

```text
NAME                  STATUS  ROLES             VERSION
etri-dev0001-jetorn   Ready   agent,edge        v1.32.10-kubeedge-v1.23.0
etri-dev0002-raspi5   Ready   agent,edge        v1.32.10-kubeedge-v1.23.0
etri-dev0003-raspi5   Ready   agent,edge        v1.32.10-kubeedge-v1.23.0
etri-ser0001-cg0msb   Ready   control-plane     v1.31.14
etri-ser0002-cgnmsb   Ready   worker            v1.31.14

etri-ser0001-cg0msb allocatable: cpu=24, memory=131496788Ki, nvidia.com/gpu=10
etri-ser0002-cgnmsb allocatable: cpu=24, memory=32000292Ki, nvidia.com/gpu=1
etri-dev0001-jetorn allocatable: cpu=6, memory=7700316Ki, arch=arm64
etri-dev0002-raspi5 allocatable: cpu=4, memory=16505776Ki, arch=arm64
etri-dev0003-raspi5 allocatable: cpu=4, memory=8154048Ki, arch=arm64
```

모든 노드의 조회 시점 taint는 `<none>`입니다. 기존 GPU label은 `gpu=on`, `gpu.platform=server`, `accelerator=nvidia-gpu`(worker)이며 custom `science-ai.io/*` label은 아직 없습니다.

### Node describe / GPU driver

명령:

```bash
kubectl describe nodes
kubectl exec -n kube-system dcgm-exporter-lhwm4 -- nvidia-smi
kubectl exec -n kube-system nvidia-device-plugin-daemonset-xqkl8 -- nvidia-smi
```

출력:

```text
NVIDIA-SMI 595.84    Driver Version: 595.84    CUDA Version: 13.2
GPU 0 NVIDIA GeForce RTX 5080    14249MiB / 16303MiB    GPU-Util 0%
```

control-plane GPU는 HAMi node annotation에서 `NVIDIA GeForce RTX 5060 Ti`, `devmem=8151`, `count=10`으로 확인됐고 worker GPU는 `NVIDIA GeForce RTX 5080`, `devmem=16303`, `count=10`입니다. `nvidia-smi`는 worker에서 이미 14249MiB 메모리가 사용 중인 것으로 관찰되어 GPU Demo는 기존 워크로드 영향 여부를 확인하면서 실행해야 합니다.

### Pods, KubeEdge

명령:

```bash
kubectl get pods -A -o wide
kubectl get pods -n kubeedge -o wide
kubectl get deployment cloudcore -n kubeedge -o jsonpath='{.spec.template.spec.containers[*].image}'
kubectl get helm list -A
```

출력 핵심:

```text
kubeedge/cloudcore-... Running 1/1 on etri-ser0001-cg0msb
kubeedge edge Mosquitto and edgemesh-agent pods are Running on all 3 edge nodes
kubeedge/cloudcore image: kubeedge/cloudcore:v1.23.0
helm: cloudcore chart 1.23.0 deployed; edgemesh chart 0.1.0 deployed
```

EdgeCore는 별도 Pod가 아니라 Edge 노드 kubelet 상태(`v1.32.10-kubeedge-v1.23.0`, `EdgeReady`)와 edgemesh/edge broker Pod 상태로 확인했습니다.

### HAMi

명령:

```bash
kubectl get pods -A -o wide
kubectl get daemonset hami-device-plugin -n kube-system -o yaml
kubectl get deployment hami-scheduler -n kube-system -o yaml
kubectl get configmap hami-scheduler-device -n kube-system -o yaml
kubectl get configmap hami-scheduler -n kube-system -o yaml
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.allocatable}{"\t"}{.metadata.annotations.hami.io/node-nvidia-register}{"\n"}{end}'
```

출력:

```text
hami-device-plugin: 2/2 Running
hami-scheduler: 1/1 Running
Helm release: hami 2.9.0, chart hami-2.9.0
device-config:
  resourceCountName: nvidia.com/gpu
  resourceMemoryName: nvidia.com/gpumem
  resourceMemoryPercentageName: nvidia.com/gpumem-percentage
  resourceCoreName: nvidia.com/gpucores
  deviceSplitCount: 10
managedResources in hami scheduler: nvidia.com/gpu, nvidia.com/gpumem,
  nvidia.com/gpucores, nvidia.com/gpumem-percentage, nvidia.com/priority
```

기존 HAMi Pod는 `privileged`, `hostPID`, 여러 `hostPath`를 사용합니다. 이것은 현재 운영 구성요소의 상태이며 mini-science-ai-os가 변경하지 않습니다. 새 Workload는 API에서 일반 Pod security context만 사용하고 `schedulerName: hami-scheduler`로 기존 scheduler만 연계합니다.

### Prometheus, Grafana, DCGM

명령:

```bash
kubectl get prometheus,alertmanager -A
kubectl get servicemonitor,podmonitor -A
kubectl get pods -n kube-system -o wide
kubectl get servicemonitor dcgm-exporter -n kube-system -o yaml
kubectl get --raw '/api/v1/namespaces/kube-system/services/http:prometheus-kube-prometheus-prometheus:9090/proxy/-/ready'
kubectl get --raw '/api/v1/namespaces/kube-system/services/http:prometheus-kube-prometheus-prometheus:9090/proxy/api/v1/query?query=DCGM_FI_DEV_GPU_UTIL'
```

출력:

```text
Prometheus prometheus-kube-prometheus-prometheus v3.10.0: Desired=1 Ready=1 Available=True
Alertmanager v0.31.1: Ready=1
Prometheus Operator, kube-state-metrics, Grafana: Running in kube-system
dcgm-exporter: 2/2 Running, image nvcr.io/nvidia/k8s/dcgm-exporter:4.5.3-4.8.2-distroless
ServiceMonitor dcgm-exporter interval=15s path=/metrics label release=prometheus
Prometheus Server is Ready.
DCGM_FI_DEV_GPU_UTIL returned RTX 5080 and RTX 5060 Ti vectors with value 0
```

### Argo CD

명령:

```bash
kubectl get applications -A
kubectl get applications -n argocd -o custom-columns=NAME:.metadata.name,SOURCE:.spec.source.path,DEST:.spec.destination.namespace,SYNC:.status.sync.status,HEALTH:.status.health.status
kubectl get application edge-orch-state-aggregator -n argocd -o yaml
```

현재 Application은 기존 `edge-orch-*`, `edgex-*`, `docs-html`, `edge-ai-llm` 구조이며 State Aggregator Application은 외부 Git repository `https://github.com/dsa04156/edge-ai-workspace.git`, path `edge-orch/state-aggregator/k8s`, automated prune/selfHeal을 사용합니다. mini-science-ai-os는 이 Application을 수정하지 않습니다. 본 프로젝트의 Argo Application은 별도 repo URL을 받아 적용할 수 있도록 제공하되, 이 local workspace가 remote Git에 publish되기 전에는 Synced를 주장하지 않습니다.

### Storage, Ingress, Registry, NetworkPolicy

명령:

```bash
kubectl get storageclass
kubectl get pv
kubectl get pvc -A
kubectl get ingress,ingressroute -A
curl -fsS http://192.168.0.56:5000/v2/_catalog
kubectl get networkpolicy -A
```

출력:

```text
local-path (default) rancher.io/local-path Delete WaitForFirstConsumer
PV/PVC: existing local-path claims are Bound; default/ollama-qwen3-data is Pending
Traefik LoadBalancer 192.168.0.56:80/443 and existing IngressRoutes are present
Registry catalog: 192.168.0.56:5000 reachable, existing repositories returned
NetworkPolicy objects exist in argocd/edgex namespaces, but kube-system has no
Calico/Cilium policy controller; kube-flannel is the observed CNI component
```

이 환경은 StorageClass가 있으므로 hostPath 우회가 필요하지 않습니다. `local-path`는 노드 로컬 저장소이므로 MLOps 데이터의 복제/백업 한계는 [disaster-recovery.md](../disaster-recovery.md)에 기록했습니다.

### Existing State Aggregator

Kubernetes 조회:

```text
Deployment default/state-aggregator: 1/1 Ready
image: 192.168.0.56:5000/state-aggregator:responsive-all-20260810-1
service: default/state-aggregator:8000
ServiceMonitor: default/state-aggregator, /metrics, interval=15s
```

로컬 코드 위치:

```text
/home/jinuk/codex-work/jinuk/edge-orch/state-aggregator
```

FastAPI route는 `/state/nodes`, `/state/devices`, `/state/summary`, `/metrics` 등 장치/EdgeX/Prometheus 관측용입니다. Science Resource Catalog API 계약(`/v1/sites`, `/v1/resources`)과 Job 권한 경계를 추가해 기존 운영 Deployment를 변경하는 것은 범위를 벗어나므로, 이 프로젝트는 별도 `resource-catalog` 서비스를 구현합니다.

## Phase 0 판단

- 다음 Phase 진행 가능: **예**.
- 즉시 재사용: HAMi 2.9.0, Prometheus Operator, Grafana, DCGM exporter, local-path, Traefik, internal registry, existing State Aggregator API.
- 새로 필요한 요소: Kueue v0.17.3, tenant namespaces/policies, MLflow/PostgreSQL/MinIO, catalog/API/MCP images.
- 주요 위험: worker RTX 5080의 기존 14249MiB 메모리 사용, Flannel NetworkPolicy enforcement 미확인, local-path 단일 노드 저장소, local workspace의 Argo Git source 부재.

