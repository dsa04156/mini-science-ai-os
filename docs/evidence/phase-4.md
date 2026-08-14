# Phase 4 evidence — Resource Catalog

## 1. Changed files

- `services/science_os/resource_catalog.py`
- `services/science_os/adapters.py`
- `apps/resource-catalog/k8s.yaml`
- `tests/test_resource_catalog.py`

## 2. Commands executed

```text
rtk kubectl port-forward -n science-ai-system svc/resource-catalog 18084:8000
rtk curl http://127.0.0.1:18084/v1/sites
rtk curl http://127.0.0.1:18084/v1/nodes
rtk curl http://127.0.0.1:18084/v1/resources
rtk curl http://127.0.0.1:18084/v1/resources/summary
rtk make validate
```

## 3. Actual results

The four endpoints returned successfully. Summary output was:

```text
{"siteCount":1,"nodeCount":5,"readyNodeCount":5,"gpuNodeCount":2,
 "resourceNames":{"count":"nvidia.com/gpu","memory":"nvidia.com/gpumem","core":"nvidia.com/gpucores"}}
```

The live response identified RTX 5060 Ti and RTX 5080, HAMI mode `hami-core`, and Prometheus-derived pressure fields. Unknown values remain `null` where the source did not provide them. `10 passed` includes the regression test that excludes Succeeded/Failed Pods from current HAMI allocation.

## 4. Problems and risks

- The existing State Aggregator was read and left unchanged; this MVP does not claim full State Aggregator API equivalence.
- Prometheus pressure queries depend on the existing node-exporter label/address model; query errors are exposed as `null` and counted in a metric.

## 5. Next phase

The Catalog is available to the tenant MCP and can be extended with the existing Kubernetes adapter, the Slurm mock adapter, and the Cloud interface.
