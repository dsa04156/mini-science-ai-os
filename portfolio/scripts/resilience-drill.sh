#!/usr/bin/env bash
set -euo pipefail

mode="${1:-plan}"
namespace="tenant-etri"
deployment="science-job-api"
selector="app.kubernetes.io/name=science-job-api"

plan() {
  cat <<'EOF'
Resilience drill plan (no cluster changes):
1. Require science-job-api desired=2, ready=2 and PDB disruptionsAllowed>=1.
2. Check /readyz through the Kubernetes Service proxy.
3. Evict exactly one selected science-job-api Pod through policy/v1 Eviction.
4. Wait for the Deployment to return to 2 Ready replicas.
5. Check /readyz again and confirm the replacement Pod UID differs.

Run only with:
  CONFIRM_RESILIENCE_DRILL=tenant-etri/science-job-api \
    bash portfolio/scripts/resilience-drill.sh run
EOF
}

run_drill() {
  [[ "${CONFIRM_RESILIENCE_DRILL:-}" == "${namespace}/${deployment}" ]] || {
    printf 'ERROR: set CONFIRM_RESILIENCE_DRILL=%s/%s.\n' "${namespace}" "${deployment}" >&2
    exit 2
  }

  desired="$(kubectl get deployment "${deployment}" -n "${namespace}" -o jsonpath='{.spec.replicas}')"
  ready="$(kubectl get deployment "${deployment}" -n "${namespace}" -o jsonpath='{.status.readyReplicas}')"
  disruptions="$(kubectl get pdb "${deployment}" -n "${namespace}" -o jsonpath='{.status.disruptionsAllowed}')"
  [[ "${desired}" == "2" && "${ready}" == "2" ]] || {
    printf 'ERROR: expected desired=2 and ready=2, got desired=%s ready=%s.\n' "${desired}" "${ready}" >&2
    exit 1
  }
  [[ "${disruptions:-0}" -ge 1 ]] || {
    printf 'ERROR: PDB currently allows no disruption.\n' >&2
    exit 1
  }

  kubectl get --raw "/api/v1/namespaces/${namespace}/services/http:${deployment}:8000/proxy/readyz" >/dev/null
  pod="$(kubectl get pods -n "${namespace}" -l "${selector}" --sort-by=.metadata.name -o jsonpath='{.items[0].metadata.name}')"
  old_uid="$(kubectl get pod "${pod}" -n "${namespace}" -o jsonpath='{.metadata.uid}')"

  kubectl create --raw "/api/v1/namespaces/${namespace}/pods/${pod}/eviction" -f - >/dev/null <<EOF
{
  "apiVersion": "policy/v1",
  "kind": "Eviction",
  "metadata": {"name": "${pod}", "namespace": "${namespace}"}
}
EOF

  kubectl rollout status deployment/"${deployment}" -n "${namespace}" --timeout=180s
  kubectl wait pod -n "${namespace}" -l "${selector}" --for=condition=Ready --timeout=180s >/dev/null
  kubectl get --raw "/api/v1/namespaces/${namespace}/services/http:${deployment}:8000/proxy/readyz" >/dev/null
  if kubectl get pods -n "${namespace}" -l "${selector}" -o jsonpath='{range .items[*]}{.metadata.uid}{"\n"}{end}' \
      | grep -Fxq "${old_uid}"; then
    printf 'ERROR: evicted Pod UID is still present.\n' >&2
    exit 1
  fi
  ready_after="$(kubectl get deployment "${deployment}" -n "${namespace}" -o jsonpath='{.status.readyReplicas}')"
  [[ "${ready_after}" == "2" ]] || { printf 'ERROR: ready replicas after drill=%s.\n' "${ready_after}" >&2; exit 1; }
  printf 'Resilience drill passed: one PDB-governed eviction, 2 Ready replicas restored, /readyz available.\n'
}

case "${mode}" in
  plan) plan ;;
  run) run_drill ;;
  -h|--help) plan ;;
  *) printf 'usage: resilience-drill.sh plan|run\n' >&2; exit 2 ;;
esac
