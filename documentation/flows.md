# Product flows

## Portal job lifecycle

Actor: ETRI researcher on the trusted internal network. Precondition: the ETRI product URL is reachable.

1. Browser opens `/portal/`; no state change.
2. Browser posts `/v1/portal/session`; API checks that automatic internal access is enabled and signs an ETRI-only HttpOnly cookie. No API token is sent to the browser.
3. Browser reads `/v1/config`, resources, and jobs using the cookie. Invalid/expired signatures return 401.
4. Browser posts a validated `ScienceJobRequest`. Cookie-authenticated writes require matching Origin or `Sec-Fetch-Site=same-origin`; otherwise 403.
5. API enforces image allowlist, resource caps, array command, fixed Namespace/Queue/Runner and submits a KFP Run.
6. KFP creates an ETRI Job. Kueue admits or holds it; scheduler/HAMi chooses a node and logical GPU allocation.
7. Kubeflow stores run metadata in MySQL and artifacts in MinIO. Browser reads status, metrics and artifacts through the API.
8. Cancel deletes only the mapped ETRI Job and terminates its linked KFP Run. Unknown IDs return 404.

Side effects: signed session cookie, ETRI ConfigMap mapping, KFP Run/Workflow, Kubernetes Job/Workload, MySQL records, MinIO objects and structured logs.

## MCP job lifecycle

Actor: ETRI agent. Precondition: it can reach `agent-runtime-mcp` and is authorized by the caller-side integration.

1. Agent calls one of six MCP tools.
2. MCP sanitizes arguments and calls only Resource Catalog or ETRI Science Job API.
3. MCP authenticates to the API with the Secret-mounted ETRI token; it never calls Kubernetes.
4. API applies the same validation and fixed-scope rules as the portal.
5. MCP writes a structured Audit event with request ID, tool, decision, linked Job and sanitized result/error.

Deny cases: disallowed image 400, forbidden fields 422, unknown Job 404, API token mismatch 401. MCP itself currently has no per-human identity or approval gate.

## Operator release flow

Actor: cluster operator with the existing kubeconfig.

1. `make bootstrap` builds the pinned image and server-side applies ETRI/shared manifests.
2. `CONFIRM_REMOVE_KIST=tenant-kist make etri-only` verifies project ownership labels before deleting only KIST project resources. Shared KFP history/storage remains.
3. `make release-check` runs static tests, live RBAC/API/MCP/dependency tests and product endpoint checks.
4. `INTERNAL_PRODUCT=READY`이면 ETRI 신뢰 내부망 제품으로 릴리스한다. 외부 공개형 제품 판정은 별도이며 TLS/OIDC, policy enforcement와 원격 DR이 필요하다.
