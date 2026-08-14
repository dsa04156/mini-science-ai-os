#!/usr/bin/env bash
set -euo pipefail

cd "${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
mkdir -p docs/evidence
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
evidence="docs/evidence/validate-${stamp}.md"
failed=0
python_bin="${PYTHON_BIN:-python3.12}"
if [[ -x .venv/bin/python ]]; then
  python_bin="${PYTHON_BIN:-.venv/bin/python}"
fi

{
  printf '# Validation evidence — %s\n\n' "${stamp}"
  printf '## Python compile\n\n```text\n'
  "${python_bin}" -m compileall -q services || failed=1
  printf 'compileall exit=%s\n```\n' "${failed}"

  printf '\n## Unit/API tests\n\n```text\n'
  if "${python_bin}" -m pytest --version >/dev/null 2>&1; then
    "${python_bin}" -m pytest -q tests || failed=1
  else
    printf 'BLOCKED: pytest is not installed in the local Python environment.\n'
    failed=1
  fi
  printf '```\n'

  printf '\n## Kustomize render\n\n```text\n'
  kubectl kustomize tenants/etri >/dev/null || failed=1
  kubectl kustomize apps/mlops >/dev/null || failed=1
  kubectl kustomize apps/kubeflow/cluster-scoped >/dev/null || failed=1
  kubectl kustomize apps/kubeflow/runtime >/dev/null || failed=1
  kubectl kustomize apps/kubeflow/tenant-launchers >/dev/null || failed=1
  kubectl kustomize apps/docs-site >/dev/null || failed=1
  kubectl kustomize clusters/lab --load-restrictor LoadRestrictionsNone >/dev/null || failed=1
  kubectl kustomize apps/kueue >/dev/null || failed=1
  for workload in workloads/cpu-demo/job.yaml workloads/gpu-demo/job.yaml; do
    kubectl create --dry-run=client -f "${workload}" -o yaml >/dev/null || failed=1
  done
  printf 'local Kustomize renders completed\n```\n'

  printf '\n## Client-side manifest validation\n\n```text\n'
  kubectl kustomize tenants/etri | kubectl create --dry-run=client -f - >/dev/null || failed=1
  kubectl kustomize apps/mlops | kubectl create --dry-run=client -f - >/dev/null || failed=1
  kubectl kustomize apps/docs-site | kubectl create --dry-run=client -f - >/dev/null || failed=1
  if kubectl get crd clusterqueues.kueue.x-k8s.io >/dev/null 2>&1; then
    kubectl kustomize clusters/lab --load-restrictor LoadRestrictionsNone | kubectl create --dry-run=client -f - >/dev/null || failed=1
  else
    printf 'DEFERRED: Kueue CRDs are not installed yet; cluster overlay render passed and client mapping will run after bootstrap.\n'
  fi
  printf 'kubectl client validation completed\n```\n'

  printf '\n## Optional tools\n\n```text\n'
  if command -v kubeconform >/dev/null 2>&1; then
    kubectl kustomize clusters/lab --load-restrictor LoadRestrictionsNone | kubeconform -strict -summary - || failed=1
  else
    printf 'BLOCKED/DEFERRED: kubeconform is not installed; kubectl client validation used.\n'
  fi
  if command -v shellcheck >/dev/null 2>&1; then
    shellcheck scripts/*.sh || failed=1
  else
    printf 'BLOCKED/DEFERRED: shellcheck is not installed.\n'
  fi
  printf '```\n'

  printf '\n## Security static checks\n\n```text\n'
  if grep -R -n -E 'privileged:[[:space:]]*true|hostPID:[[:space:]]*true|hostNetwork:[[:space:]]*true|hostPath:' tenants apps/resource-catalog apps/mlops apps/kubeflow apps/docs-site workloads; then
    printf 'BLOCKED: forbidden host/privileged field found in new workload manifests.\n'
    failed=1
  else
    printf 'PASS: no forbidden host/privileged fields in project workload manifests.\n'
  fi
  if grep -R -n -E 'password:|token:[[:space:]]+[^R]|secret-key:[[:space:]]+[^R]' tenants apps/mlops; then
    printf 'REVIEW: possible secret literal found; placeholders and secretKeyRefs must be checked.\n'
  fi
  printf '```\n'

  if (( failed == 0 )); then printf '\nValidation completed.\n'; else printf '\nValidation has BLOCKED/failed checks.\n'; fi
} 2>&1 | tee "${evidence}"

printf 'Validation evidence written to %s\n' "${evidence}"
exit "${failed}"
