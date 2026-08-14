#!/usr/bin/env bash
set -euo pipefail

cd "${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
mkdir -p docs/evidence
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
evidence="docs/evidence/test-${stamp}.md"
failed=0
port=18180
pids=()

cleanup() {
  for pid in "${pids[@]:-}"; do kill "${pid}" >/dev/null 2>&1 || true; done
}
trap cleanup EXIT

{
  printf '# Live verification evidence — %s\n\n' "${stamp}"
  printf '## ETRI least-privilege RBAC negative tests\n\n```text\n'
  for resource in jobs pods secrets; do
      result="$(kubectl auth can-i get "${resource}" --as=system:serviceaccount:tenant-etri:agent-runtime -n tenant-etri || true)"
      printf 'tenant-etri agent-runtime -> tenant-etri/%s: %s\n' "${resource}" "${result}"
      [[ "${result}" == "no" ]] || failed=1
  done
  api_secret="$(kubectl auth can-i get secrets --as=system:serviceaccount:tenant-etri:science-job-api -n tenant-etri || true)"
  runner_default="$(kubectl auth can-i create jobs --as=system:serviceaccount:kubeflow:pipeline-runner-etri -n default || true)"
  printf 'tenant-etri science-job-api -> tenant-etri/secrets: %s\n' "${api_secret}"
  printf 'pipeline-runner-etri -> default/jobs create: %s\n' "${runner_default}"
  [[ "${api_secret}" == "no" && "${runner_default}" == "no" ]] || failed=1
  printf '```\n'

  printf '\n## ETRI API session and validation tests\n\n```text\n'
  kubectl port-forward -n tenant-etri svc/science-job-api "${port}:8000" >/tmp/mini-science-api-test.log 2>&1 &
  pids+=("$!")
  sleep 3
  etri_token="$(kubectl get secret tenant-api-token -n tenant-etri -o jsonpath='{.data.token}' | base64 -d)"
  unauth="$(curl -sS -o /tmp/mini-science-unauth.json -w '%{http_code}' "http://127.0.0.1:${port}/v1/jobs")"
  printf 'tenant-etri unauthenticated GET: HTTP %s (expected 401)\n' "${unauth}"
  [[ "${unauth}" == "401" ]] || failed=1
  cookie_jar="$(mktemp)"
  session="$(curl -sS -c "${cookie_jar}" -o /tmp/mini-science-session.json -w '%{http_code}' -X POST "http://127.0.0.1:${port}/v1/portal/session")"
  cookie_config="$(curl -sS -b "${cookie_jar}" -o /tmp/mini-science-config.json -w '%{http_code}' "http://127.0.0.1:${port}/v1/config")"
  csrf="$(curl -sS -b "${cookie_jar}" -o /tmp/mini-science-csrf.json -w '%{http_code}' -X DELETE "http://127.0.0.1:${port}/v1/jobs/0123456789ab")"
  docs="$(curl -sS -o /tmp/mini-science-docs.json -w '%{http_code}' "http://127.0.0.1:${port}/docs")"
  rm -f "${cookie_jar}"
  printf 'automatic portal session: HTTP %s (expected 200)\n' "${session}"
  printf 'session-authenticated config: HTTP %s (expected 200)\n' "${cookie_config}"
  printf 'cookie DELETE without Origin: HTTP %s (expected 403)\n' "${csrf}"
  printf 'production API docs disabled: HTTP %s (expected 404)\n' "${docs}"
  [[ "${session}" == "200" && "${cookie_config}" == "200" && "${csrf}" == "403" && "${docs}" == "404" ]] || failed=1
  bad_image='{"project":"security-test","image":"evil.example.invalid/malware:1","command":["python","-c","print(1)"],"resources":{"cpu":"100m","memory":"128Mi"},"datasetVersion":"v1","experiment":"security","priority":"normal"}'
  bad_image_status="$(curl -sS -o /tmp/mini-science-bad-image.json -w '%{http_code}' -X POST -H "X-Science-Token: ${etri_token}" -H 'Content-Type: application/json' -d "${bad_image}" "http://127.0.0.1:${port}/v1/jobs")"
  printf 'disallowed image: HTTP %s (expected 400)\n' "${bad_image_status}"
  [[ "${bad_image_status}" == "400" ]] || failed=1
  privileged='{"project":"security-test","image":"192.168.0.56:5000/mini-science-ai-os:0.3.1","command":["python","-c","print(1)"],"resources":{"cpu":"100m","memory":"128Mi"},"datasetVersion":"v1","experiment":"security","privileged":true}'
  privileged_status="$(curl -sS -o /tmp/mini-science-privileged.json -w '%{http_code}' -X POST -H "X-Science-Token: ${etri_token}" -H 'Content-Type: application/json' -d "${privileged}" "http://127.0.0.1:${port}/v1/jobs")"
  printf 'privileged input: HTTP %s (expected 422)\n' "${privileged_status}"
  [[ "${privileged_status}" == "422" ]] || failed=1
  hostpath='{"project":"security-test","image":"192.168.0.56:5000/mini-science-ai-os:0.3.1","command":["cat","/host/etc/passwd"],"resources":{"cpu":"100m","memory":"128Mi"},"datasetVersion":"v1","experiment":"security","hostPath":"/"}'
  hostpath_status="$(curl -sS -o /tmp/mini-science-hostpath.json -w '%{http_code}' -X POST -H "X-Science-Token: ${etri_token}" -H 'Content-Type: application/json' -d "${hostpath}" "http://127.0.0.1:${port}/v1/jobs")"
  printf 'hostPath input: HTTP %s (expected 422)\n' "${hostpath_status}"
  [[ "${hostpath_status}" == "422" ]] || failed=1
  printf '```\n'

  printf '\n## Agent MCP self-scope test\n\n```text\n'
  if kubectl get pod -n tenant-etri -l app.kubernetes.io/name=agent-runtime -o name | head -1 | grep -q .; then
    kubectl exec -n tenant-etri deploy/agent-runtime -- python -c 'import asyncio; from science_os.mcp_server import list_available_resources; print(asyncio.run(list_available_resources()))' 2>&1 || failed=1
    printf 'Agent called list_available_resources through the MCP implementation.\n'
    printf '\n## Agent MCP self job lifecycle\n\n```text\n'
    if kubectl exec -i -n tenant-etri deploy/agent-runtime -- python - <<'PY'
import asyncio
import json

from science_os.mcp_server import cancel_own_job, get_job_status, submit_science_job


async def main() -> None:
    submitted = await submit_science_job(
        {
            "project": "mcp-live",
            "image": "192.168.0.56:5000/mini-science-ai-os:0.3.1",
            "command": ["python", "-c", "print('mcp-live')"],
            "resources": {"cpu": "100m", "memory": "128Mi"},
            "datasetVersion": "mcp-v1",
            "experiment": "mcp-live",
            "priority": "normal",
        }
    )
    job_id = submitted["jobId"]
    status = await get_job_status(job_id)
    cancelled = await cancel_own_job(job_id)
    print(json.dumps({"submitted": submitted, "status": status, "cancelled": cancelled}, sort_keys=True))


asyncio.run(main())
PY
    then
      printf 'Agent submitted, inspected, and cancelled its own Job through MCP.\n'
    else
      failed=1
    fi
    printf '```\n'
    printf '\n## MCP Streamable HTTP protocol\n\n```text\n'
    if kubectl exec -i -n tenant-etri deploy/agent-runtime -- python - <<'PY'
import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main() -> None:
    async with streamable_http_client("http://127.0.0.1:8000/mcp") as streams:
        read_stream, write_stream = streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            listed = await session.list_tools()
            called = await session.call_tool("list_available_resources", {})
            print(json.dumps({"tools": [tool.name for tool in listed.tools], "resultType": type(called).__name__}, sort_keys=True))


asyncio.run(main())
PY
    then
      printf 'MCP Streamable HTTP initialize/list/call passed.\n'
    else
      failed=1
    fi
    printf '```\n'
  else
    printf 'BLOCKED: tenant-etri agent-runtime Pod is not ready.\n'
    failed=1
  fi
  printf '```\n'

  printf '\n## Kueue and workload state\n\n```text\n'
  kubectl get crd workloads.kueue.x-k8s.io >/dev/null 2>&1 || { printf 'BLOCKED: Kueue CRD is absent.\n'; failed=1; }
  kubectl get clusterqueue,resourceflavor,localqueue -A -l science-ai.io/managed-by=mini-science-ai-os 2>&1 || failed=1
  kubectl get jobs,pods,workloads -A -l science-ai.io/managed-by=mini-science-ai-os 2>&1 || true
  printf '```\n'

  printf '\n## NetworkPolicy enforcement\n\n```text\n'
  policy_engine="$(kubectl get pods -n kube-system -o name 2>/dev/null | grep -Ei 'calico|cilium|antrea|ovn' || true)"
  if [[ -z "${policy_engine}" ]]; then
    printf 'BLOCKED: no Calico/Cilium/Antrea/OVN policy controller observed; Flannel-only CNI cannot prove NetworkPolicy enforcement.\n'
  else
    printf 'Policy controller observed: %s\n' "${policy_engine}"
  fi
  printf '```\n'

  printf '\n## Kubeflow Pipelines, artifact storage and Prometheus\n\n```text\n'
  kubectl get deploy -n kubeflow ml-pipeline ml-pipeline-ui metadata-grpc-deployment mysql 2>&1 || failed=1
  kubectl get svc -n kubeflow ml-pipeline ml-pipeline-ui mysql seaweedfs 2>&1 || failed=1
  kubectl get --raw '/api/v1/namespaces/kubeflow/services/http:ml-pipeline:8888/proxy/apis/v2beta1/healthz' 2>&1 || failed=1
  kubectl get pods,svc,pvc -n science-ai-mlops -o wide 2>&1 || failed=1
  kubectl get prometheusrule -n science-ai-system mini-science-ai-os-alerts 2>&1 || failed=1
  kubectl get servicemonitor -A -l science-ai.io/managed-by=mini-science-ai-os 2>&1 || failed=1
  printf '```\n'

  printf '\n## ETRI-only product endpoint\n\n```text\n'
  if kubectl get namespace tenant-kist >/dev/null 2>&1; then
    printf 'FAIL: tenant-kist Namespace still exists.\n'
    failed=1
  else
    printf 'tenant-kist Namespace: absent\n'
  fi
  root_status="$(curl -sS -o /tmp/mini-science-product-root.html -w '%{http_code}' -H 'Host: science-workspace.192.168.0.56.nip.io' http://192.168.0.56/)"
  portal_status="$(curl -sS -o /tmp/mini-science-product-portal.html -w '%{http_code}' -H 'Host: science-workspace.192.168.0.56.nip.io' http://192.168.0.56/portal/)"
  ready_status="$(curl -sS -o /tmp/mini-science-product-ready.json -w '%{http_code}' -H 'Host: science-workspace.192.168.0.56.nip.io' http://192.168.0.56/readyz)"
  printf 'product root redirect: HTTP %s (expected 307)\n' "${root_status}"
  printf 'product portal: HTTP %s (expected 200)\n' "${portal_status}"
  printf 'product readiness: HTTP %s (expected 200)\n' "${ready_status}"
  [[ "${root_status}" == "307" && "${portal_status}" == "200" && "${ready_status}" == "200" ]] || failed=1
  grep -q 'NAIS Science Workspace' /tmp/mini-science-product-portal.html || failed=1
  grep -q '"version":"0.3.1"' /tmp/mini-science-product-ready.json || failed=1
  grep -q '"profile":"internal-production"' /tmp/mini-science-product-ready.json || failed=1
  grep -q '"accessMode":"trusted-network"' /tmp/mini-science-product-ready.json || failed=1
  printf '```\n'

  if (( failed == 0 )); then printf '\nLive verification completed.\n'; else printf '\nLive verification contains failed or BLOCKED checks.\n'; fi
} 2>&1 | tee "${evidence}"

printf 'Test evidence written to %s\n' "${evidence}"
exit "${failed}"
