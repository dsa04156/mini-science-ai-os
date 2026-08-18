# Workspace live evidence overlay

This package adds an interview-ready live operations dashboard to NAIS Science Workspace. It combines the existing `Site → Node → GPU → Workload` placement view with real Kubernetes capacity, Kueue admission, Prometheus component health, DCGM physical GPU telemetry and the Agent trust boundary. The overview also presents a live `Kubeflow → MLflow Run → candidate model → Grafana` evidence spine sourced from the real KFP and MLflow APIs. Science Job detail remains joined to its observed HAMi allocation.

The canonical source files under `services/science_os` are root-owned in this workspace, so the changed files are kept as an explicit image overlay. The runtime image is based on `0.3.1` and published as `0.3.8-neutral-ui`.

## Build

```bash
tar -czf /tmp/science-topology-context.tar.gz -C workspace-topology Dockerfile overrides
kubectl create configmap science-ai-topology-source -n science-ai-build \
  --from-file=context.tar.gz=/tmp/science-topology-context.tar.gz \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl delete job science-topology-image-builder -n science-ai-build --ignore-not-found
kubectl apply -f workspace-topology/kaniko-job.yaml
kubectl wait --for=condition=complete job/science-topology-image-builder -n science-ai-build --timeout=20m
```

## Deploy

```bash
bash workspace-topology/deploy.sh
```

## Test

The overlay is not a standalone Python package. This command reproduces the
Docker build by copying the canonical package and applying the overlay before
running its focused tests:

```bash
bash workspace-topology/test.sh
```
