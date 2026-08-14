# Kueue integration

Kueue is not present in the Phase 0 CRD list. The project uses the official v0.17.3 release manifest, which supports Kubernetes 1.29+ and therefore matches the observed v1.31.14 server. `make bootstrap` applies this remote manifest server-side only to the upstream `kueue-system` namespace; it does not touch `kube-system`.

The custom queue objects in `queues.yaml` use the ResourceFlavor label selectors already observed on the cluster:

- `environment=cloud`
- `kubernetes.io/arch=amd64`

HAMi resource names were discovered from the live `hami-scheduler-device` ConfigMap before being copied into project configuration: `nvidia.com/gpu`, `nvidia.com/gpumem`, and `nvidia.com/gpucores`. If HAMi is upgraded, rerun `make inventory` and update the explicit values only after re-discovery.

