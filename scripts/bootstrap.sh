#!/usr/bin/env bash
set -euo pipefail

cd "${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
mkdir -p docs/evidence
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
evidence="docs/evidence/bootstrap-${stamp}.md"
failed=0

{
  printf '# Bootstrap evidence — %s\n\n' "${stamp}"
  printf 'No existing operating Namespace is modified by this script.\n\n'
  kubectl apply -f policies/namespaces.yaml || failed=1
  kubectl apply -f apps/mlops/namespace.yaml || failed=1
  kubectl apply -f tenants/etri/namespace.yaml || failed=1

  printf '\n## Kubeflow Pipelines 2.17.0 cluster-scoped resources\n'
  kubectl apply --server-side -k apps/kubeflow/cluster-scoped || failed=1
  for crd in workflows.argoproj.io workflowtaskresults.argoproj.io; do
    kubectl wait --for=condition=Established "crd/${crd}" --timeout=5m || failed=1
  done
  bash scripts/ensure-secrets.sh || failed=1

  if [[ "${BUILD_IMAGES:-1}" == "1" ]]; then
    if ! bash scripts/build-images.sh; then
      printf '\nBLOCKED: custom runtime image build failed; continuing manifest deployment for evidence.\n'
      failed=1
    fi
  else
    printf 'BLOCKED: BUILD_IMAGES=0; runtime image was not built by this run.\n'
    failed=1
  fi

  if kubectl get crd workloads.kueue.x-k8s.io >/dev/null 2>&1; then
    printf 'Kueue CRD already exists; upstream installation skipped.\n'
  else
    kubectl apply --server-side -k apps/kueue || failed=1
  fi
  if ! kubectl wait --for=condition=Available deployment/kueue-controller-manager -n kueue-system --timeout=10m; then
    printf 'BLOCKED: Kueue controller did not become Available.\n'
    failed=1
  fi
  kubectl apply --server-side -f apps/kueue/queues.yaml || failed=1

  printf '\n## Kubeflow Pipelines runtime and tenant launchers\n'
  kubectl apply --server-side -k apps/kubeflow/runtime || failed=1
  kubectl kustomize clusters/lab --load-restrictor LoadRestrictionsNone | kubectl apply --server-side -f - || failed=1

  for deployment in ml-pipeline ml-pipeline-ui metadata-grpc-deployment metadata-writer mysql workflow-controller; do
    kubectl rollout status "deployment/${deployment}" -n kubeflow --timeout=10m || failed=1
  done
  kubectl wait --for=condition=complete job/kubeflow-minio-init -n kubeflow --timeout=5m || failed=1

  kubectl rollout status deployment/resource-catalog -n science-ai-system --timeout=5m 2>&1 || true
  kubectl rollout status deployment/science-job-api -n tenant-etri --timeout=5m 2>&1 || failed=1
  kubectl rollout status deployment/agent-runtime -n tenant-etri --timeout=5m 2>&1 || failed=1
  kubectl rollout status statefulset/minio -n science-ai-mlops --timeout=10m 2>&1 || failed=1
  kubectl get pods -A -l science-ai.io/managed-by=mini-science-ai-os -o wide || true
  kubectl get deploy,svc,pvc -n kubeflow || true
  kubectl get clusterqueue,resourceflavor,localqueue -A -l science-ai.io/managed-by=mini-science-ai-os || true
  kubectl get ingress,pdb -n tenant-etri || true

  if [[ -n "${GITOPS_REPO_URL:-}" ]]; then
    tmpapp="$(mktemp)"
    trap 'rm -f "${tmpapp}"' EXIT
    sed "s|https://REPLACE_WITH_PUBLISHED_REPOSITORY/mini-science-ai-os.git|${GITOPS_REPO_URL}|g" argocd/app-of-apps.yaml >"${tmpapp}"
    kubectl apply --server-side -f "${tmpapp}" || failed=1
    printf 'Argo CD App-of-Apps submitted for %s.\n' "${GITOPS_REPO_URL}"
  else
    printf 'BLOCKED/DEFERRED: Argo CD Application not applied because this workspace has no published Git repository.\n'
  fi

  if (( failed == 0 )); then
    printf '\nBootstrap commands completed without a reported error. Inspect rollout and verification evidence before declaring PASS.\n'
  else
    printf '\nBootstrap completed with one or more BLOCKED/failed steps.\n'
  fi
} 2>&1 | tee "${evidence}"

printf 'Bootstrap evidence written to %s\n' "${evidence}"
exit "${failed}"
