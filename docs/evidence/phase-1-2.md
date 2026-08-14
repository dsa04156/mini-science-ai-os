# Phase 1–2 evidence — project structure and tenant isolation

## 1. Changed files

- `README.md`, `Makefile`, `.gitignore`
- `tenants/base/*`, `tenants/etri/*`, `tenants/kist/*`
- `policies/namespaces.yaml`
- `apps/build/*`, `scripts/*`
- `docs/architecture.md`, `docs/security-decisions.md`, `docs/threat-model.md`

## 2. Commands executed

```text
rtk make validate
rtk make bootstrap
rtk kubectl auth can-i get jobs --as=system:serviceaccount:tenant-etri:agent-runtime -n tenant-kist
rtk kubectl auth can-i get pods --as=system:serviceaccount:tenant-kist:agent-runtime -n tenant-etri
rtk make test
```

## 3. Actual results

- `make validate`: Python compile exit 0, `10 passed`, all project Kustomize renders and client-side mappings passed.
- `make bootstrap` (`bootstrap-20260810T091348Z.md`): both tenant API/MCP Deployments rolled out; `tenant-etri` and `tenant-kist` LocalQueues applied; existing Secret keys were preserved.
- Cross-tenant RBAC checks in `test-20260810T092026Z.md`: jobs, pods and secrets returned `no` for both directions.
- Tenant PSA labels, ResourceQuota and LimitRange are present in both tenant namespaces.

## 4. Problems and risks

- Flannel was the only observed CNI dataplane; no Calico/Cilium/Antrea/OVN policy controller was found. NetworkPolicy objects exist, but live isolation is BLOCKED.
- Tenant authentication is a per-tenant token MVP, not central user identity. Token rotation requires a controlled Secret update and rollout.

## 5. Next phase

Phase 3–7 was allowed to proceed because tenant admission, RBAC boundaries and the project rollouts were live. NetworkPolicy enforcement remains an explicit residual risk.
