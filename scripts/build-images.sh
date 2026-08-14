#!/usr/bin/env bash
set -euo pipefail

cd "${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
mkdir -p docs/evidence
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
evidence="docs/evidence/build-images-${stamp}.md"
image_tag="${IMAGE_TAG:-$(tr -d '[:space:]' < VERSION)}"
image="192.168.0.56:5000/mini-science-ai-os:${image_tag}"

{
  printf '# Image build evidence — %s\n\n' "${stamp}"
  printf 'Image: `%s`\n\n' "${image}"
  # Remove only the legacy project build Job from the first failed attempt.
  kubectl delete job science-image-builder -n science-ai-system --ignore-not-found >/dev/null 2>&1 || true
  if curl -fsS -H 'Accept: application/vnd.docker.distribution.manifest.v2+json' \
      "http://192.168.0.56:5000/v2/mini-science-ai-os/manifests/${image_tag}" >/dev/null 2>&1; then
    printf 'Existing image tag found; build skipped (idempotent).\n'
    exit 0
  fi

  kubectl apply -f policies/namespaces.yaml
  kubectl apply -f apps/build/namespace.yaml
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "${tmpdir}"' EXIT
  tar -czf "${tmpdir}/context.tar.gz" Dockerfile requirements.txt services
  kubectl create configmap science-ai-source -n science-ai-build --from-file=context.tar.gz="${tmpdir}/context.tar.gz" --dry-run=client -o yaml | kubectl apply -f -
  # Remove only the legacy project build Job from the first failed attempt.
  kubectl delete job science-image-builder -n science-ai-system --ignore-not-found
  kubectl delete job science-image-builder -n science-ai-build --ignore-not-found
  sed "s#mini-science-ai-os:0.3.1#mini-science-ai-os:${image_tag}#" apps/build/kaniko-job.yaml | kubectl apply -f -
  if ! kubectl wait --for=condition=complete job/science-image-builder -n science-ai-build --timeout=20m; then
    printf '\nBLOCKED: Kaniko build did not complete.\n'
    kubectl get job,pod -n science-ai-build -l science-ai.io/build=true -o wide || true
    kubectl logs -n science-ai-build job/science-image-builder --all-containers=true || true
    exit 1
  fi
  kubectl logs -n science-ai-build job/science-image-builder --all-containers=true
  if ! curl -fsS "http://192.168.0.56:5000/v2/mini-science-ai-os/tags/list"; then
    printf '\nBLOCKED: registry tag was not observable after a successful build job.\n'
    exit 1
  fi
  printf '\nImage build PASS.\n'
} 2>&1 | tee "${evidence}"

printf 'Build evidence written to %s\n' "${evidence}"
