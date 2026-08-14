#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${root}"
failed=0

fail_if_found() {
  local description="$1"
  shift
  if rg -n "$@"; then
    printf 'FAIL: %s\n' "${description}" >&2
    failed=1
  else
    printf 'PASS: %s\n' "${description}"
  fi
}

printf '== High-confidence secret and injection checks ==\n'
fail_if_found 'no private-key or cloud access-key material' \
  -g '!docs/evidence/**' -g '!tmp/**' -g '!.git/**' \
  'BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY|AKIA[0-9A-Z]{16}' .
fail_if_found 'no Python shell=True or os.system execution' \
  -g '*.py' 'shell[[:space:]]*=[[:space:]]*True|os\.system[[:space:]]*\(' services portfolio workspace-topology
fail_if_found 'no dynamic browser code execution' \
  -g '*.js' -g '*.html' "eval[[:space:]]*\\(|new Function|set(Time|Inter)val[[:space:]]*\\([[:space:]]*['\\\"]" services open-source-docs workspace-topology

printf '\n== Workload privilege checks ==\n'
fail_if_found 'project workloads do not request host or privileged access' \
  -g '*.yaml' 'privileged:[[:space:]]*true|hostPID:[[:space:]]*true|hostNetwork:[[:space:]]*true|hostPath:' \
  tenants apps/resource-catalog apps/mlops workloads portfolio

printf '\n== Required application controls ==\n'
rg -q 'ConfigDict\(extra="forbid"' services/science_os/job_api.py || { printf 'FAIL: Pydantic write models must reject extra fields.\n' >&2; failed=1; }
rg -q 'httponly=True' services/science_os/job_api.py || { printf 'FAIL: portal cookie must be HttpOnly.\n' >&2; failed=1; }
rg -q 'samesite="strict"' services/science_os/job_api.py || { printf 'FAIL: portal cookie must be SameSite Strict.\n' >&2; failed=1; }
rg -q 'Content-Security-Policy' services/science_os/job_api.py || { printf 'FAIL: portal CSP is missing.\n' >&2; failed=1; }
rg -q 'docs_url="/docs" if _docs_enabled else None' services/science_os/job_api.py || { printf 'FAIL: production docs gate is missing.\n' >&2; failed=1; }
rg -q 'shell=False' portfolio/slurm_adapter.py || { printf 'FAIL: SLURM runner must explicitly disable shell execution.\n' >&2; failed=1; }
printf 'PASS: schema, cookie, CSP, docs and SLURM execution controls are present.\n'

printf '\n== Review-only signals ==\n'
inner_html_count="$(rg -g '*.js' -g '*.html' -c '\.innerHTML|insertAdjacentHTML' services open-source-docs workspace-topology 2>/dev/null | awk -F: '{sum += $2} END {print sum + 0}')"
printf 'REVIEW: %s DOM HTML sink occurrence(s); existing portal paths require escaping tests.\n' "${inner_html_count}"
if rg -q "script-src[^\n]*'unsafe-inline'" open-source-docs; then
  printf 'REVIEW: static documentation CSP permits inline script; no untrusted document content is expected.\n'
fi
printf 'REVIEW: NetworkPolicy enforcement and per-user identity remain documented live gaps.\n'

exit "${failed}"
