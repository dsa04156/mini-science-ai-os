#!/usr/bin/env bash
set -euo pipefail

cd "${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

printf 'VERSION=%s\n' "$(tr -d '[:space:]' < VERSION)"
kubectl get deployment,pod,service,ingress,pdb -n tenant-etri -l science-ai.io/managed-by=mini-science-ai-os
kubectl get localqueue -n tenant-etri tenant-etri
kubectl get clusterqueue science-shared
if kubectl get namespace tenant-kist >/dev/null 2>&1; then
  printf 'KIST_NAMESPACE=present\n'
  exit 1
fi
printf 'KIST_NAMESPACE=absent\n'
curl --fail --silent --show-error --location --output /dev/null --write-out 'PRODUCT_HTTP=%{http_code}\n' http://science-workspace.192.168.0.56.nip.io/
ready="$(curl --fail --silent --show-error http://science-workspace.192.168.0.56.nip.io/readyz)"
printf 'PRODUCT_READY=%s\n' "${ready}"
grep -q '"profile":"internal-production"' <<<"${ready}"
grep -q '"accessMode":"trusted-network"' <<<"${ready}"
printf 'INTERNAL_PRODUCT=READY\n'
