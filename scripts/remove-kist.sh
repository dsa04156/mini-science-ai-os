#!/usr/bin/env bash
set -euo pipefail

cd "${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
mkdir -p docs/evidence
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
evidence="docs/evidence/etri-only-${stamp}.md"

{
  printf '# ETRI-only migration evidence — %s\n\n' "${stamp}"
  printf 'Shared Kubeflow, Kueue, HAMi, Prometheus, Grafana and storage are preserved.\n\n'

  if kubectl get namespace tenant-kist >/dev/null 2>&1; then
    owner="$(kubectl get namespace tenant-kist -o jsonpath='{.metadata.labels.science-ai\.io/managed-by}')"
    tenant="$(kubectl get namespace tenant-kist -o jsonpath='{.metadata.labels.science-ai\.io/tenant-name}')"
    printf 'Discovered namespace owner=%s tenant=%s.\n' "${owner}" "${tenant}"
    if [[ "${owner}" != "mini-science-ai-os" || "${tenant}" != "kist" ]]; then
      printf 'BLOCKED: tenant-kist ownership labels do not match this project; nothing deleted.\n'
      exit 1
    fi
    if [[ "${CONFIRM_REMOVE_KIST:-}" != "tenant-kist" ]]; then
      printf 'No deletion performed. Re-run with CONFIRM_REMOVE_KIST=tenant-kist after reviewing this inventory.\n\n```text\n'
      kubectl get all,role,rolebinding,serviceaccount,resourcequota,limitrange,networkpolicy,localqueue -n tenant-kist
      printf '```\n'
      exit 2
    fi

    printf '\n## Removed project resources\n\n```text\n'
    kubectl delete rolebinding pipeline-runner-kist-kubeflow -n kubeflow --ignore-not-found
    kubectl delete serviceaccount pipeline-runner-kist -n kubeflow --ignore-not-found
    kubectl delete namespace tenant-kist --wait=true --timeout=5m
    printf '```\n'
  else
    printf 'tenant-kist Namespace is already absent; namespace removal is idempotently complete.\n'
    kubectl delete rolebinding pipeline-runner-kist-kubeflow -n kubeflow --ignore-not-found
    kubectl delete serviceaccount pipeline-runner-kist -n kubeflow --ignore-not-found
  fi

  if kubectl get namespace tenant-kist >/dev/null 2>&1; then
    printf 'BLOCKED: tenant-kist still exists after migration.\n'
    exit 1
  fi
  printf '\nPASS: tenant-kist and its Kubeflow launcher identity are absent. Historical KFP metadata and shared storage were preserved.\n'
} 2>&1 | tee "${evidence}"

printf 'ETRI-only evidence written to %s\n' "${evidence}"
