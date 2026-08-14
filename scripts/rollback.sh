#!/usr/bin/env bash
set -euo pipefail

cd "${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
mkdir -p docs/evidence
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
evidence="docs/evidence/rollback-${stamp}.md"

{
  printf '# Rollback plan/evidence — %s\n\n' "${stamp}"
  printf 'Safe default: inspect only. Existing HAMi, Prometheus, Grafana, Argo CD, KubeEdge, and State Aggregator are never deleted by this script.\n\n'
  printf '## Project resources\n\n```text\n'
  kubectl get all -A -l science-ai.io/managed-by=mini-science-ai-os 2>&1 || true
  printf '```\n\n'
  if [[ "${CONFIRM_ROLLBACK:-}" == "DELETE_PROJECT_NAMESPACES" ]]; then
    printf 'CONFIRM_ROLLBACK=DELETE_PROJECT_NAMESPACES supplied; deleting only tenant-etri, science-ai-system, science-ai-mlops, science-ai-build.\n'
    kubectl delete namespace tenant-etri science-ai-system science-ai-mlops science-ai-build --ignore-not-found
  else
    printf 'No deletion performed. To remove project namespaces after review, explicitly run:\n\n'
    printf 'CONFIRM_ROLLBACK=DELETE_PROJECT_NAMESPACES make rollback\n'
  fi
} 2>&1 | tee "${evidence}"

printf 'Rollback evidence written to %s\n' "${evidence}"
