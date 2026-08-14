#!/usr/bin/env bash
set -euo pipefail

cd "${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
umask 077

ensure_secret() {
  local namespace="$1" name="$2" key="$3" value="$4"
  if ! kubectl get secret "${name}" -n "${namespace}" >/dev/null 2>&1; then
    kubectl create secret generic "${name}" -n "${namespace}" --from-literal="${key}=${value}" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
    printf 'Secret %s/%s created without printing its value\n' "${namespace}" "${name}"
    return
  fi
  local present
  present="$(kubectl get secret "${name}" -n "${namespace}" -o go-template="{{if index .data \"${key}\"}}present{{end}}")"
  if [[ "${present}" == "present" ]]; then
    printf 'Secret %s/%s key %s exists; preserving value\n' "${namespace}" "${name}" "${key}"
    return
  fi
  kubectl patch secret "${name}" -n "${namespace}" --type=merge -p "{\"stringData\":{\"${key}\":\"${value}\"}}" >/dev/null
  printf 'Secret %s/%s key %s added without printing its value\n' "${namespace}" "${name}" "${key}"
}

new_token() { openssl rand -hex 32; }

ensure_secret science-ai-mlops platform-minio access-key "${PLATFORM_MINIO_ACCESS_KEY:-$(new_token)}"
ensure_secret science-ai-mlops platform-minio secret-key "${PLATFORM_MINIO_SECRET_KEY:-$(new_token)}"
ensure_secret kubeflow mysql-secret username "${KUBEFLOW_MYSQL_USER:-root}"
ensure_secret kubeflow mysql-secret password "${KUBEFLOW_MYSQL_PASSWORD:-$(new_token)}"

# Copy only base64-encoded Secret data through stdin; values never appear in logs or Git.
kubectl get secret platform-minio -n science-ai-mlops -o json \
  | jq '{apiVersion:"v1",kind:"Secret",metadata:{name:"kubeflow-artifact-store",namespace:"kubeflow"},type:"Opaque",data:{accesskey:.data["access-key"],secretkey:.data["secret-key"]}}' \
  | kubectl apply -f - >/dev/null
printf 'Kubeflow object-store Secret synchronized without printing values\n'
ensure_secret tenant-etri tenant-api-token token "${TENANT_ETRI_API_TOKEN:-$(new_token)}"
