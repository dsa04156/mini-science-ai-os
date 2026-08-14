#!/usr/bin/env bash
set -euo pipefail

cd "${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
mkdir -p docs/evidence
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
evidence="docs/evidence/destroy-demo-${stamp}.md"

{
  printf '# Demo cleanup evidence — %s\n\n' "${stamp}"
  printf 'Deleting only Jobs selected by science-ai.io/managed-by=mini-science-ai-os and science-ai.io/demo=true.\n\n'
  kubectl get jobs -A -l science-ai.io/managed-by=mini-science-ai-os,science-ai.io/demo=true -o wide || true
  kubectl delete jobs -A -l science-ai.io/managed-by=mini-science-ai-os,science-ai.io/demo=true --ignore-not-found
  kubectl get workloads -A -l science-ai.io/managed-by=mini-science-ai-os,science-ai.io/demo=true -o wide 2>&1 || true
  printf '\nRemaining project workloads (non-demo resources are intentionally preserved):\n'
  kubectl get jobs,pods -A -l science-ai.io/managed-by=mini-science-ai-os -o wide || true
} 2>&1 | tee "${evidence}"

printf 'Demo cleanup evidence written to %s\n' "${evidence}"

