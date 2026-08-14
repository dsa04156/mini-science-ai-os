# Agent and automation map

## ETRI MCP runtime

- Trigger/owner: explicit call by an ETRI agent integration; platform operator owns deployment.
- Automatic behavior: none beyond executing the selected tool. No autonomous scheduler or policy mutation.
- Read inputs: Resource Catalog summary, ETRI Job status, metrics, artifacts and experiment runs.
- Exact tools: `list_available_resources`, `submit_science_job`, `get_job_status`, `get_run_metrics`, `list_experiment_runs`, `cancel_own_job`.
- Exact outbound APIs: ETRI Science Job API and Resource Catalog HTTP only.
- Steering: MCP tool descriptions and server instructions.
- Hard guardrails: no Kubernetes token/client, fixed ETRI API URL/token, API Pydantic validation, fixed Namespace/SA/Queue, Registry/resource limits.
- Output contract: JSON-compatible dictionaries from the downstream API; downstream HTTP errors fail the tool call.
- Side effects: submit and cancel are agent-triggered writes; list/status/metrics are reads.
- Audit: JSON event to stdout and `/tmp/audit.jsonl`, with recursive secret masking.
- Limits: Pod CPU/memory, non-root/read-only rootfs, DNS rebinding protection and NetworkPolicy manifests.
- Kill switch: scale `tenant-etri/agent-runtime` to zero or remove its Service while retaining the Science Job API.

Missing product controls: per-user agent identity, approval gates for submit/cancel, durable centralized audit, explicit call rate limit and retry/backoff policy.
