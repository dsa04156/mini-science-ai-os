# Phase 0 inventory

조사 시각: 2026-08-10 (Asia/Seoul)

이 문서는 기존 리소스를 변경하지 않고 `kubectl` 조회로 수집한 기준선이다. 원문에 가까운 명령과 주요 출력은 [evidence/phase-0.md](evidence/phase-0.md)에 보관한다. 값이 확인되지 않은 항목은 추측하지 않고 `unknown`으로 남겼다.

## 클러스터와 노드

실행한 명령:

```text
rtk kubectl version --output=yaml
rtk kubectl get nodes -o wide
rtk kubectl get nodes --show-labels
rtk kubectl describe nodes
rtk kubectl get node -o json
rtk kubectl top nodes
```

확인 결과:

| Node | 역할/상태 | Arch | CPU allocatable | Memory allocatable | GPU allocatable | 주요 사실 |
|---|---|---:|---:|---:|---:|---|
| `etri-dev0001-jetorn` | edge, Ready/EdgeReady | arm64 | 6 | 약 7.7Gi | unknown | KubeEdge v1.23.0 계열 |
| `etri-dev0002-raspi5` | edge, Ready/EdgeReady | arm64 | 4 | 약 16.5Gi | unknown | Raspberry Pi |
| `etri-dev0003-raspi5` | edge, Ready/EdgeReady | arm64 | 4 | 약 8.1Gi | unknown | Raspberry Pi |
| `etri-ser0001-cg0msb` | control-plane, Ready | amd64 | 24 | 131496788Ki | `nvidia.com/gpu: 10` | RTX 5060 Ti, HAMI virtual count 10 |
| `etri-ser0002-cgnmsb` | worker, Ready | amd64 | 24 | 32000292Ki | `nvidia.com/gpu: 1` | RTX 5080, HAMI virtual count 10 |

Kubernetes client/server는 `v1.31.14`, Kustomize는 `v5.4.2`다. Edge node kubelet은 `v1.32.10-kubeedge-v1.23.0`으로 보인다. 기존 labels/taints는 보존한다. 본 프로젝트는 `science-ai.io/*` prefix를 사용하며 자동 label patch를 하지 않는다. 적용 예정 patch는 [node-label-plan.md](node-label-plan.md)에만 출력했다.

`etri-ser0002-cgnmsb`의 기존 `nvidia-smi` 조사에서는 Driver `595.84`, CUDA `13.2`, `14249MiB/16303MiB` 메모리 사용이 관찰됐다. 표시된 프로세스가 없는 상태도 확인됐으므로, GPU 여유와 실제 원인은 별도 검증이 필요하다. GPU 성능 격리는 이 값만으로 주장하지 않는다.

## KubeEdge

실행한 명령:

```text
rtk kubectl get pods -n kubeedge -o wide
rtk kubectl get nodes -l node-role.kubernetes.io/edge
rtk kubectl get helmrelease -A
```

`kubeedge/cloudcore:v1.23.0` CloudCore Pod와 edge broker/edgemesh 구성요소가 Running이며 세 edge node가 EdgeReady로 보인다. EdgeCore는 별도 Pod가 아니므로 node status와 kubelet 버전으로만 확인했다. Edge에서의 Science Job 실행은 이 MVP에서 자동 선택하지 않는다.

## HAMi/GPU

실행한 명령:

```text
rtk kubectl get pods -n kube-system -l app.kubernetes.io/instance=hami
rtk kubectl get crd | rtk rg 'hami|device'
rtk kubectl get configmap hami-scheduler-device -n kube-system -o yaml
rtk kubectl get nodes -o json
```

HAMi Helm release `hami`, chart/app `2.9.0`가 `kube-system`에 있고 scheduler 및 device-plugin이 Running이다. 실제 설정에서 확인한 리소스 이름은 다음과 같다.

```text
count   = nvidia.com/gpu
memory  = nvidia.com/gpumem
core    = nvidia.com/gpucores
percent = nvidia.com/gpumem-percentage
split   = 10
```

`nvidia.com/gpu`, `nvidia.com/gpumem`, `nvidia.com/gpucores`만 이번 Kueue quota에 사용하고, percent 이름은 catalog에서 관찰 가능한 경우에만 표시한다. 리소스 이름을 추측해 기존 HAMi를 덮어쓰지 않는다. 기존 HAMi Pod의 privileged/hostPID/hostPath는 기존 운영 구성요소의 상태이며 본 프로젝트가 변경하지 않는다.

## 관측성

실행한 명령:

```text
rtk kubectl get helmrelease -A
rtk kubectl get prometheus,alertmanager -A
rtk kubectl get pods -A | rtk rg 'prometheus|grafana|dcgm'
rtk kubectl get servicemonitor,podmonitor -A
rtk kubectl get --raw '/api/v1/query?query=DCGM_FI_DEV_GPU_UTIL'
```

Prometheus Operator 기반 `kube-prometheus-stack` release `prometheus`, chart `82.14.1`, app `v0.89.0`가 `kube-system`에 있다. Prometheus `v3.10.0`, Alertmanager `v0.31.1`, Grafana image `grafana:12.4.2`, DCGM exporter `4.5.3-4.8.2-distroless`가 확인됐다. Prometheus readiness는 `Prometheus Server is Ready.`였고 DCGM query는 RTX 5060 Ti/5080 series를 반환했다. 프로젝트 rule/ServiceMonitor는 `release=prometheus` label로 기존 selector에 참여하도록 만들었다.

Phase 0의 Pod/Service 조회에서 `influxdb` 리소스는 관찰되지 않았다. 따라서 InfluxDB를 새로 설치하거나 기존 시계열 구성을 추정해 변경하지 않았다.

## Argo CD와 기존 State Aggregator

`argocd` namespace에 기존 Applications가 있으며 대부분 Synced/Healthy이나 `edge-ai-llm`은 조사 시점에 Unknown/Progressing이었다. 기존 `edge-orch-state-aggregator` Application과 repository/path를 읽기 전용으로 확인했고 변경하지 않는다.

기존 State Aggregator는 `default/state-aggregator`, image `192.168.0.56:5000/state-aggregator:responsive-all-20260810-1`, Service port `8000`, ServiceMonitor `/metrics`였다. 로컬 코드 `/home/jinuk/codex-work/jinuk/edge-orch/state-aggregator`에는 `/state/nodes`, `/state/devices`, `/state/summary`, `/metrics` 계열 route가 있다. MVP Resource Catalog는 결합도를 낮추기 위해 이 서비스를 수정하지 않고 Kubernetes/Prometheus adapter interface를 별도로 제공한다.

## Storage, ingress, registry, network

| 항목 | 조사 결과 | MVP 영향 |
|---|---|---|
| StorageClass | `local-path`, default, `rancher.io/local-path`, WaitForFirstConsumer, Delete, expansion 없음 | Postgres/MinIO PVC에 사용. node-local 백업 위험을 문서화 |
| Ingress | Traefik LoadBalancer `192.168.0.56` | 새 Ingress는 만들지 않고 port-forward를 기본 절차로 사용 |
| Registry | `http://192.168.0.56:5000/v2/_catalog` 응답 가능 | Kaniko push를 시도. 인증/HTTPS는 확인되지 않음 |
| CNI/NetworkPolicy | Flannel Pod 확인; Calico/Cilium/Antrea/OVN policy controller는 발견되지 않음 | NetworkPolicy manifest는 제공하나 enforcement는 BLOCKED로 검증 |
| Docker | local `docker info`는 permission denied | cluster Kaniko Build Job을 사용 |

## 충돌 방지 결론

- 제품 Namespace: `science-ai-system`, `science-ai-mlops`, `tenant-etri`, Kueue가 없을 때만 `kueue-system`. `tenant-kist`는 ETRI-only 전환에서 제거됐다.
- 수정하지 않는 범위: `kube-system`, 기존 HAMi/Prometheus/Grafana/DCGM/Argo/State Aggregator, 기존 workload.
- cluster-scoped 추가는 Kueue가 없을 때의 upstream Kueue 설치와 프로젝트 `ClusterQueue`, `ResourceFlavor`, `PriorityClass`, PrometheusRule에 한정한다.
- Argo Application은 published Git URL을 받기 전까지 적용하지 않는다.
