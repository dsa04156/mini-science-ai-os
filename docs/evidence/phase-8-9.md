# Phase 8–9 evidence — monitoring and GitOps

## 1. Changed files

- `monitoring/grafana/science-ai-overview.json`
- `policies/prometheus-rules.yaml`
- ServiceMonitors in `apps/resource-catalog/k8s.yaml` and `tenants/base/services.yaml`
- `argocd/app-of-apps.yaml`, `argocd/applications/mini-science-ai-os.yaml`
- `scripts/bootstrap.sh`, `scripts/test.sh`

## 2. Commands executed

```text
rtk kubectl get servicemonitor -A -l science-ai.io/managed-by=mini-science-ai-os
rtk kubectl get --raw '.../api/v1/targets'
rtk kubectl get --raw '.../api/v1/query?query=science_mcp_tool_calls_total'
rtk kubectl get --raw '.../api/v1/rules'
rtk kubectl get prometheusrule -n science-ai-system mini-science-ai-os-alerts
```

## 3. Actual results

- Resource Catalog, both Science Job APIs and both Agent MCP endpoints had Prometheus targets `health=up`.
- The MCP target returned `science_mcp_tool_calls_total{result="success",tool="list_available_resources"} 1`; Catalog returned `science_catalog_requests_total{route="summary"}`.
- The project PrometheusRule loaded nine rules; all had `health=ok`. At the final check the project alerts were inactive, including `ScienceMlflowUnavailable` after the false `/metrics` target was removed.
- DCGM queries returned GPU utilization, framebuffer used, temperature and power for RTX 5060 Ti/5080.
- Dashboard JSON and alert rules are in the repository; no existing Grafana dashboards were overwritten.

## 4. Problems and risks

- Grafana dashboard import and visual rendering were not live-tested; status is PARTIAL.
- `kubeconform` and `shellcheck` were not installed. Kubectl client validation and the project test suite passed instead; those tools remain DEFERRED.
- Argo CD App-of-Apps was not applied because no published Git repository URL was available. Existing Applications were not modified, so Synced/Healthy for this project is BLOCKED.

## 5. Next phase

Publish the repository, set `GITOPS_REPO_URL`, apply only the project App-of-Apps, then verify its Application Synced/Healthy/Drift states. Import the dashboard into the existing Grafana after a reviewed folder/ownership decision.
