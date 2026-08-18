#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
overlay_root="${repo_root}/workspace-topology/overrides/science_os"
test_root="$(mktemp -d)"
trap 'rm -rf "${test_root}"' EXIT

# Reproduce the image build: start from the canonical package and apply the
# workspace-topology files over it before importing science_os in tests.
cp -a "${repo_root}/services/science_os" "${test_root}/science_os"
cp "${overlay_root}/job_api.py" "${test_root}/science_os/job_api.py"
cp "${overlay_root}/resource_catalog.py" "${test_root}/science_os/resource_catalog.py"
cp -a "${overlay_root}/portal/." "${test_root}/science_os/portal/"

cd "${repo_root}"
PYTHONPATH="${test_root}" uv run --isolated \
  --with-requirements requirements.txt \
  --with-requirements requirements-dev.txt \
  -- python -m pytest -q \
  --override-ini "pythonpath=${test_root}" \
  workspace-topology/tests
