# Phase 6–7 evidence — Science Job API, MCP and audit

## 1. Changed files

- `services/science_os/job_api.py`
- `services/science_os/mcp_server.py`
- `services/science_os/common.py`
- `tenants/base/services.yaml`, `tenants/base/rbac.yaml`
- `scripts/test.sh`
- `tests/test_job_api.py`, `tests/test_mcp.py`, `tests/test_common.py`

## 2. Commands executed

```text
rtk make test
rtk kubectl exec -i -n tenant-etri deploy/agent-runtime -- python - <<'PY' ... MCP ClientSession ... PY
rtk kubectl logs -n tenant-etri deploy/agent-runtime --tail=80
```

## 3. Actual results

From `test-20260810T092026Z.md`:

```text
unauthenticated GET: HTTP 401
tenant-etri token against tenant-kist API: HTTP 401
disallowed image: HTTP 400
privileged input: HTTP 422
hostPath input: HTTP 422
```

MCP self lifecycle returned HTTP 200 for submit, status and cancel. The MCP Streamable HTTP client listed all six required tools and called `list_available_resources`; result type was `CallToolResult`. Structured JSON audit output included request ID, tenant, tool name, sanitized arguments, authorization decision and result/error fields. The direct Kubernetes ServiceAccount is not used by the MCP server.

## 4. Problems and risks

- Authentication is tenant token based; no OIDC/user identity mapping is implemented in the MVP.
- Audit output is container stdout/ephemeral `/tmp` by default. A durable log sink is required for production retention and tamper resistance.
- NetworkPolicy enforcement remains BLOCKED by the observed Flannel-only dataplane.

## 5. Next phase

Prometheus ServiceMonitors and the Grafana/alert artifacts can consume API/MCP metrics. Production must add central identity, durable audit storage and an enforcing CNI/policy dataplane.
