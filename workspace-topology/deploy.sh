#!/usr/bin/env bash
set -euo pipefail

image="${TOPOLOGY_IMAGE:-192.168.0.56:5000/mini-science-ai-os:0.3.2-topology}"
package_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

kubectl apply -k "${package_root}"
kubectl -n science-ai-system set image deployment/resource-catalog "resource-catalog=${image}"
kubectl -n tenant-etri set image deployment/science-job-api "api=${image}"
kubectl -n tenant-etri rollout restart deployment/science-job-api
kubectl -n science-ai-system rollout status deployment/resource-catalog --timeout=180s
kubectl -n tenant-etri rollout status deployment/science-job-api --timeout=180s
