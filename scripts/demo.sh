#!/usr/bin/env bash
set -euo pipefail

cd "${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
mkdir -p docs/evidence
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
evidence="docs/evidence/demo-${stamp}.md"
port=18080
pf_log="/tmp/mini-science-ai-os-port-forward-${stamp}.log"
pf_pid=""

cleanup() {
  if [[ -n "${pf_pid}" ]]; then
    kill "${pf_pid}" >/dev/null 2>&1 || true
    wait "${pf_pid}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

{
  printf '# Demo evidence — %s\n\n' "${stamp}"
  if ! kubectl get deployment science-job-api -n tenant-etri >/dev/null 2>&1; then
    printf 'BLOCKED: tenant-etri Science Job API is not deployed. Run make bootstrap first.\n'
    exit 1
  fi
  token="$(kubectl get secret tenant-api-token -n tenant-etri -o jsonpath='{.data.token}' | base64 -d)"
  kubectl port-forward -n tenant-etri svc/science-job-api "${port}:8000" >"${pf_log}" 2>&1 &
  pf_pid=$!
  for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:${port}/healthz" >/dev/null 2>&1; then break; fi
    sleep 1
  done
  if ! curl -fsS "http://127.0.0.1:${port}/healthz"; then
    printf '\nBLOCKED: port-forward/API health check failed.\n'
    sed -n '1,80p' "${pf_log}" || true
    exit 1
  fi
  printf '\n\n## CPU Science Job\n\n'
  cpu_body='{"project":"physical-ai","image":"192.168.0.56:5000/mini-science-ai-os:0.3.1","command":["python","-m","science_os.demo","--mode","cpu"],"resources":{"cpu":"500m","memory":"512Mi"},"datasetVersion":"factory-v1","experiment":"defect-detection-mvp","priority":"normal","gitCommit":"demo"}'
  cpu_response="$(curl -fsS -X POST "http://127.0.0.1:${port}/v1/jobs" -H "X-Science-Token: ${token}" -H 'X-Science-Demo: true' -H 'Content-Type: application/json' -d "${cpu_body}")"
  printf '%s\n' "${cpu_response}"
  cpu_id="$(python3.12 -c 'import json,sys; print(json.load(sys.stdin)["jobId"])' <<<"${cpu_response}")"

  printf '\n## Queue hold and pending job\n\n'
  hold_body='{"project":"queue-hold","image":"192.168.0.56:5000/mini-science-ai-os:0.3.1","command":["python","-c","import time; time.sleep(600)"],"resources":{"cpu":"6","memory":"12Gi"},"datasetVersion":"factory-v1","experiment":"queue-test","priority":"low","gitCommit":"demo"}'
  hold_response="$(curl -fsS -X POST "http://127.0.0.1:${port}/v1/jobs" -H "X-Science-Token: ${token}" -H 'X-Science-Demo: true' -H 'Content-Type: application/json' -d "${hold_body}")"
  printf 'hold: %s\n' "${hold_response}"
  queued_body='{"project":"queue-wait","image":"192.168.0.56:5000/mini-science-ai-os:0.3.1","command":["python","-c","import time; time.sleep(60)"],"resources":{"cpu":"3","memory":"4Gi"},"datasetVersion":"factory-v1","experiment":"queue-test","priority":"normal","gitCommit":"demo"}'
  queued_response="$(curl -fsS -X POST "http://127.0.0.1:${port}/v1/jobs" -H "X-Science-Token: ${token}" -H 'X-Science-Demo: true' -H 'Content-Type: application/json' -d "${queued_body}")"
  printf 'queued: %s\n' "${queued_response}"

  printf '\n## GPU HAMi jobs\n\n'
  gpu_body='{"project":"physical-ai","image":"192.168.0.56:5000/mini-science-ai-os:0.3.1","command":["python","-m","science_os.demo","--mode","gpu"],"resources":{"cpu":"500m","memory":"512Mi","acceleratorVendor":"nvidia","gpuCount":1,"gpuMemoryMiB":1024,"gpuCorePercent":10},"datasetVersion":"factory-v1","experiment":"defect-detection-gpu-mvp","priority":"normal","gitCommit":"demo"}'
  gpu_one="$(curl -fsS -X POST "http://127.0.0.1:${port}/v1/jobs" -H "X-Science-Token: ${token}" -H 'X-Science-Demo: true' -H 'Content-Type: application/json' -d "${gpu_body}")"
  gpu_two="$(curl -fsS -X POST "http://127.0.0.1:${port}/v1/jobs" -H "X-Science-Token: ${token}" -H 'X-Science-Demo: true' -H 'Content-Type: application/json' -d "${gpu_body}")"
  printf 'gpu-1: %s\ngpu-2: %s\n' "${gpu_one}" "${gpu_two}"

  sleep 5
  printf '\n## Created resources\n\n```text\n'
  kubectl get jobs,pods -A -l science-ai.io/managed-by=mini-science-ai-os,science-ai.io/demo=true -o wide || true
  # Kueue Workload objects do not inherit the Job's managed-by/demo labels.
  kubectl get workloads -n tenant-etri -o wide 2>&1 || true
  printf '```\n\n## GPU metric snapshot\n\n```text\n'
  kubectl get --raw '/api/v1/namespaces/kube-system/services/http:prometheus-kube-prometheus-prometheus:9090/proxy/api/v1/query?query=DCGM_FI_DEV_GPU_UTIL' 2>&1 || true
  printf '\n```\n\nCPU job id: `%s`\n' "${cpu_id}"
  printf '\nGPU interpretation: pod admission and DCGM/HAMi observations must be checked together. Logical HAMi limits are not physical performance isolation.\n'
} 2>&1 | tee "${evidence}"

printf 'Demo evidence written to %s\n' "${evidence}"
