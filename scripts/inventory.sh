#!/usr/bin/env bash
set -euo pipefail

cd "${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
mkdir -p docs/evidence
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="docs/evidence/inventory-${stamp}.md"

{
  printf '# Inventory command output — %s\n\n' "${stamp}"
  printf 'Context: '; kubectl config current-context 2>&1 || true
  printf '\n## kubectl version\n\n```text\n'; kubectl version --output=yaml 2>&1 || true; printf '```\n'
  printf '\n## kubectl get nodes -o wide\n\n```text\n'; kubectl get nodes -o wide 2>&1 || true; printf '```\n'
  printf '\n## kubectl get nodes --show-labels\n\n```text\n'; kubectl get nodes --show-labels 2>&1 || true; printf '```\n'
  printf '\n## kubectl describe nodes\n\n```text\n'; kubectl describe nodes 2>&1 || true; printf '```\n'
  printf '\n## kubectl get pods -A\n\n```text\n'; kubectl get pods -A -o wide 2>&1 || true; printf '```\n'
  printf '\n## kubectl get crd\n\n```text\n'; kubectl get crd 2>&1 || true; printf '```\n'
  printf '\n## kubectl get storageclass\n\n```text\n'; kubectl get storageclass 2>&1 || true; printf '```\n'
  printf '\n## kubectl get pv\n\n```text\n'; kubectl get pv 2>&1 || true; printf '```\n'
  printf '\n## kubectl get pvc -A\n\n```text\n'; kubectl get pvc -A 2>&1 || true; printf '```\n'
  printf '\n## kubectl top nodes\n\n```text\n'; kubectl top nodes 2>&1 || true; printf '```\n'
  printf '\n## kubectl get applications -A\n\n```text\n'; kubectl get applications -A 2>&1 || true; printf '```\n'
  printf '\n## kubectl get servicemonitor,podmonitor -A\n\n```text\n'; kubectl get servicemonitor,podmonitor -A 2>&1 || true; printf '```\n'
  printf '\n## kubectl get node -o json (summary only)\n\n```text\n'; kubectl get nodes -o custom-columns=NAME:.metadata.name,ARCH:.status.nodeInfo.architecture,ALLOCATABLE:.status.allocatable,TAINTS:.spec.taints 2>&1 || true; printf '```\n'
  printf '\n## HAMi and KubeEdge\n\n```text\n'; kubectl get pods -A -o wide 2>&1 | grep -Ei 'hami|cloudcore|edgecore|edgemesh|dcgm|nvidia' || true; kubectl get configmap hami-scheduler-device -n kube-system -o yaml 2>&1 || true; printf '```\n'
  printf '\n## Prometheus and ingress\n\n```text\n'; kubectl get prometheus,alertmanager,ingress,ingressroute -A 2>&1 || true; printf '```\n'
  printf '\n## NetworkPolicy and registry\n\n```text\n'; kubectl get networkpolicy -A 2>&1 || true; curl -fsS http://192.168.0.56:5000/v2/_catalog 2>&1 || true; printf '\n```\n'
} | tee "${out}"

printf 'Inventory evidence written to %s\n' "${out}"

