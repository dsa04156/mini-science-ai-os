#!/usr/bin/env bash
set -euo pipefail

cd "${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
mkdir -p docs/evidence
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
evidence="docs/evidence/release-check-${stamp}.md"

{
  printf '# ETRI product release check — %s\n\n' "${stamp}"
  printf '## Static validation\n\n```text\n'
  make validate
  printf '```\n\n## Live verification\n\n```text\n'
  make test
  printf '```\n\n## Product status\n\n```text\n'
  make status
  printf '```\n\nPASS: ETRI product release gate completed.\n'
} 2>&1 | tee "${evidence}"

printf 'Release evidence written to %s\n' "${evidence}"
