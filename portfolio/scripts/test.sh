#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${root}"

cache_dir="$(mktemp -d)"
cleanup() { rm -rf "${cache_dir}"; }
trap cleanup EXIT
export PYTHONPYCACHEPREFIX="${cache_dir}/pycache"

if python3 -m pytest --version >/dev/null 2>&1; then
  python3 -m compileall -q services portfolio
  python3 -m pytest -q tests portfolio/tests
elif command -v uv >/dev/null 2>&1; then
  uv run --isolated \
    --with-requirements requirements.txt \
    --with-requirements requirements-dev.txt \
    -- python -m compileall -q services portfolio
  uv run --isolated \
    --with-requirements requirements.txt \
    --with-requirements requirements-dev.txt \
    -- python -m pytest -q tests portfolio/tests
else
  printf 'ERROR: pytest is unavailable and uv is not installed.\n' >&2
  exit 1
fi

bash -n scripts/*.sh portfolio/scripts/*.sh
bash portfolio/scripts/security-check.sh
bash portfolio/scripts/recovery-drill.sh plan >/dev/null
bash portfolio/scripts/resilience-drill.sh plan >/dev/null
python3 -m portfolio.slurm_adapter plan \
  --name ci-smoke --script portfolio/examples/train.sh --cpus 2 --memory-mb 1024 >/dev/null

printf 'Portfolio check passed.\n'
