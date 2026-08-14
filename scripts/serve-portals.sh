#!/usr/bin/env bash
set -euo pipefail

etri_port="${ETRI_PORT:-8090}"
bind_address="${PORTAL_BIND_ADDRESS:-0.0.0.0}"

children=()
cleanup() {
  if ((${#children[@]})); then
    kill "${children[@]}" 2>/dev/null || true
    wait "${children[@]}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

start_portal() {
  local namespace="$1"
  local port="$2"
  kubectl get deployment science-job-api -n "${namespace}" >/dev/null
  kubectl port-forward --address="${bind_address}" -n "${namespace}" svc/science-job-api "${port}:8000" &
  children+=("$!")
}

start_portal tenant-etri "${etri_port}"

for endpoint in "http://127.0.0.1:${etri_port}/portal/"; do
  for _ in {1..30}; do
    if curl --fail --silent --show-error "${endpoint}" >/dev/null; then
      break
    fi
    sleep 1
  done
  curl --fail --silent --show-error "${endpoint}" >/dev/null
done

printf 'ETRI portal: http://%s:%s/portal/\n' "${bind_address}" "${etri_port}"
printf 'Stable product URL: http://science-workspace.192.168.0.56.nip.io/portal/\n'
printf 'Press Ctrl-C to stop the ETRI port-forward.\n'
if ! wait -n "${children[@]}"; then
  printf 'The portal port-forward stopped. Run make portal to reconnect.\n' >&2
  exit 1
fi
