"use strict";

const state = {
  config: null,
  jobs: [],
  resources: null,
  topology: null,
  operations: null,
  activeView: "overview",
  statusFilter: "all",
  search: "",
  selectedJobId: null,
  refreshing: false,
};

const byId = (id) => document.getElementById(id);
const loginView = byId("login-view");
const workspace = byId("workspace");
const jobForm = byId("job-form");
const dialog = byId("job-dialog");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function displayValue(value, fallback = "확인 불가") {
  return value === null || value === undefined || value === "" ? fallback : String(value);
}

function publicIdentifier(value, fallback = "—") {
  return displayValue(value, fallback)
    .replaceAll(/tenant-etri/gi, "internal-workspace")
    .replaceAll(/etri-lab/gi, "research-lab")
    .replaceAll(/etri/gi, "lab");
}

function statusClass(status) {
  const value = String(status || "pending").toLowerCase();
  if (value === "submitting") return "submitted";
  if (["canceled", "cancelled"].includes(value)) return "failed";
  return ["running", "succeeded", "pending", "submitted", "failed", "terminating"].includes(value) ? value : "neutral";
}

function effectiveStatus(job) {
  const kubeStatus = statusClass(job?.status);
  const kfp = String(job?.kubeflow?.state || "").replace(/^State\./, "").toUpperCase();
  if (["FAILED", "ERROR"].includes(kfp)) return "failed";
  if (["CANCELED", "CANCELLED"].includes(kfp)) return "failed";
  if (["CANCELING", "CANCELLING"].includes(kfp)) return "terminating";
  if (kfp === "SUCCEEDED") return "succeeded";
  if (kfp === "RUNNING" && ["pending", "submitted", "neutral"].includes(kubeStatus)) return "running";
  return kubeStatus;
}

function statusLabel(status) {
  const labels = { running: "실행 중", succeeded: "완료", pending: "대기", submitted: "제출됨", failed: "실패", terminating: "취소 중" };
  const value = String(status || "pending").toLowerCase();
  return labels[value] || displayValue(status, "알 수 없음");
}

function kfpLabel(value) {
  const raw = String(value || "UNKNOWN").replace(/^State\./, "").toUpperCase();
  const labels = { RUNNING: "실행", SUCCEEDED: "완료", FAILED: "실패", PENDING: "대기", SKIPPED: "건너뜀", CANCELED: "취소", CANCELING: "취소 중", SUBMITTING: "제출 중", UNKNOWN: "확인 불가" };
  return labels[raw] || raw;
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(date);
}

function jsonText(value) {
  return escapeHtml(JSON.stringify(value ?? {}, null, 2));
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...options, headers, credentials: "same-origin" });
  let payload = null;
  try { payload = await response.json(); } catch (_) { payload = null; }
  if (!response.ok) {
    if (response.status === 401 && options.authFailure !== false) showConnection("세션이 만료되었습니다. 다시 연결해 주세요.", true);
    const detail = payload && payload.detail;
    if (Array.isArray(detail)) {
      throw new Error(detail.map((item) => `${(item.loc || []).slice(1).join(".")}: ${item.msg}`).join(" · "));
    }
    throw new Error(typeof detail === "string" ? detail : `요청 실패 (${response.status})`);
  }
  return payload;
}

function toast(message, type = "success") {
  const item = document.createElement("div");
  item.className = `toast ${type === "error" ? "error" : ""}`;
  item.textContent = message;
  byId("toast-region").appendChild(item);
  window.setTimeout(() => item.remove(), 4200);
}

function setBusy(button, busy, label) {
  if (!button) return;
  if (!button.dataset.originalLabel) button.dataset.originalLabel = button.textContent;
  button.disabled = busy;
  button.textContent = busy ? label : button.dataset.originalLabel;
}

function showConnection(message = "현재 기관의 자원과 실행 이력을 안전하게 연결하고 있습니다.", failed = false) {
  loginView.hidden = false;
  workspace.hidden = true;
  byId("connection-message").textContent = message;
  byId("retry-connection").hidden = !failed;
  const progress = document.querySelector(".connection-progress");
  if (progress) progress.hidden = failed;
}

function showWorkspace() {
  loginView.hidden = true;
  workspace.hidden = false;
  byId("tenant-sidebar").textContent = "INTERNAL";
  byId("platform-version").textContent = `${state.config.edition || "Internal"} Workspace · v${state.config.version || "unknown"}`;
  byId("summary-tenant").textContent = "INTERNAL";
  byId("summary-namespace").textContent = publicIdentifier(state.config.namespace);
  byId("summary-queue").textContent = state.config.localQueue || "—";
  byId("summary-runtime").textContent = `${Math.round((state.config.limits?.jobMaxSeconds || 0) / 60)}분`;
  byId("image-input").value = state.config.defaultImage || "";
  byId("registry-help").textContent = `허용: ${(state.config.allowedRegistries || []).join(", ") || "확인 불가"}`;
  const gpuInput = jobForm.elements.gpuCount;
  if (gpuInput && state.config.limits?.gpuCount !== undefined) gpuInput.max = String(state.config.limits.gpuCount);
}

async function reconnectPortal() {
  state.config = null;
  state.jobs = [];
  state.resources = null;
  state.topology = null;
  state.operations = null;
  if (dialog.open) dialog.close();
  showConnection();
  try {
    const sessionResponse = await fetch("/v1/portal/session", { method: "POST", credentials: "same-origin" });
    if (!sessionResponse.ok) throw new Error(`자동 세션 연결 실패 (${sessionResponse.status})`);
    state.config = await api("/v1/config", { authFailure: false });
  } catch (error) {
    showConnection(error.message || "워크스페이스에 연결할 수 없습니다.", true);
    return;
  }
  showWorkspace();
  await refreshAll();
}

function queueReason(job) {
  const conditions = job.queue?.conditions || [];
  const condition = conditions.find((item) => item.status === "False") || conditions.at(-1);
  return condition?.reason || condition?.message || (job.queue?.admission ? "Admitted" : "대기 사유 확인 중");
}

function renderOverview() {
  const total = state.jobs.length;
  const running = state.jobs.filter((job) => effectiveStatus(job) === "running").length;
  const pending = state.jobs.filter((job) => ["pending", "submitted"].includes(effectiveStatus(job))).length;
  const succeeded = state.jobs.filter((job) => effectiveStatus(job) === "succeeded").length;
  byId("stat-total").textContent = String(total);
  byId("stat-total-note").textContent = total ? `${succeeded}개 완료` : "아직 제출된 작업 없음";
  byId("stat-running").textContent = String(running);
  byId("stat-pending").textContent = String(pending);
  byId("nav-job-count").textContent = String(total);
  byId("stat-gpu").textContent = state.resources ? String(state.resources.gpuNodeCount ?? "—") : "—";
  byId("stat-gpu-note").textContent = state.resources ? `${state.resources.readyNodeCount ?? "—"}/${state.resources.nodeCount ?? "—"} 노드 Ready` : "Resource Catalog 확인 불가";

  const recent = byId("recent-jobs");
  if (!state.jobs.length) {
    recent.innerHTML = '<div class="empty-state"><div class="empty-symbol">◇</div><h3>첫 작업을 시작해 보세요</h3><p>새 작업 메뉴에서 CPU 또는 GPU 실행을 제출할 수 있습니다.</p></div>';
  } else {
    recent.innerHTML = state.jobs.slice(0, 5).map((job) => `
      <button class="job-item" type="button" data-job-id="${escapeHtml(job.jobId)}">
        <span class="job-identity"><strong>${escapeHtml(job.project || job.name)}</strong><small>${escapeHtml(job.experiment || job.jobId)}</small></span>
        <span class="status-pill ${effectiveStatus(job)}">${escapeHtml(statusLabel(effectiveStatus(job)))}</span>
        <span class="job-time">${escapeHtml(formatDate(job.createdAt))}</span>
      </button>`).join("");
  }
  recent.querySelectorAll("[data-job-id]").forEach((button) => button.addEventListener("click", () => openDetail(button.dataset.jobId)));
  renderResources();
}

function renderResources() {
  const target = byId("resource-content");
  const health = byId("catalog-health");
  if (!state.resources) {
    health.textContent = "연결 실패";
    health.className = "status-pill failed";
    target.innerHTML = '<p class="notice">Resource Catalog 응답을 가져오지 못했습니다. 작업 API 기능은 계속 사용할 수 있습니다.</p>';
    return;
  }
  health.textContent = `${state.resources.readyNodeCount ?? 0} Ready`;
  health.className = "status-pill succeeded";
  const gpu = (state.resources.gpuNodes || [])[0];
  const accelerator = gpu?.accelerator || {};
  const total = Number(accelerator.totalMemoryMiB);
  const allocated = Number(accelerator.allocatedMemoryMiB);
  const hasCapacity = Number.isFinite(total) && total > 0 && Number.isFinite(allocated);
  const percent = hasCapacity ? Math.max(0, Math.min(100, (allocated / total) * 100)) : 0;
  target.innerHTML = `
    <div class="resource-main"><strong>${escapeHtml(state.resources.readyNodeCount ?? "—")}</strong><span>/ ${escapeHtml(state.resources.nodeCount ?? "—")} nodes ready</span></div>
    <div class="capacity-row"><div class="capacity-label"><span>GPU Memory 논리 할당</span><span>${hasCapacity ? `${allocated.toLocaleString()} / ${total.toLocaleString()} MiB` : "확인 불가"}</span></div><progress class="capacity-track" max="100" value="${percent.toFixed(1)}">${percent.toFixed(1)}%</progress></div>
    <div class="resource-meta"><div><small>GPU 모델</small><strong>${escapeHtml(displayValue(accelerator.model))}</strong></div><div><small>할당 모드</small><strong>${escapeHtml(displayValue(accelerator.mode))}</strong></div><div><small>Count Resource</small><strong>${escapeHtml(displayValue(state.resources.resourceNames?.count))}</strong></div><div><small>GPU Node</small><strong>${escapeHtml(publicIdentifier(gpu?.node))}</strong></div></div>`;
}

function finiteNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function fixedMetric(value, digits = 0, suffix = "") {
  const number = finiteNumber(value);
  return number === null ? "—" : `${number.toFixed(digits)}${suffix}`;
}

function compactNodeName(value) {
  const text = String(value || "");
  const match = text.match(/-(dev|ser)(\d{4})-/i);
  if (!match) return text;
  const role = match[1].toLowerCase() === "ser" ? "GPU" : "EDGE";
  return `${role} ${Number(match[2])}`;
}

function componentByName(name) {
  return state.operations?.platform?.components?.find((item) => item.name === name);
}

function serviceOrigin(lanHost, institutionHost) {
  const host = location.hostname.endsWith(".10.254.192.217.nip.io") ? institutionHost : lanHost;
  return `http://${host}`;
}

function evidencePipelineStatus(id, ready, label) {
  const stateLabel = byId(id);
  stateLabel.textContent = label;
  stateLabel.closest("li").dataset.status = ready === true ? "ready" : ready === false ? "degraded" : "unknown";
}

function renderMlopsEvidence() {
  const evidence = state.operations?.mlops || {};
  const kfp = evidence.kfp || {};
  const mlflow = evidence.mlflow || {};
  const run = mlflow.run || {};
  const model = mlflow.model || {};
  const grafana = componentByName("Grafana");

  const kfpReady = kfp.status === "ready" ? String(kfp.state).toUpperCase() === "SUCCEEDED" : null;
  const runReady = mlflow.status === "ready" ? String(run.status).toUpperCase() === "FINISHED" : null;
  const modelReady = mlflow.status === "ready" ? String(model.status).toUpperCase() === "READY" && model.alias === "candidate" : null;
  const grafanaReady = grafana ? grafana.status === "ready" : null;

  evidencePipelineStatus("evidence-kfp-state", kfpReady, kfp.status === "ready" ? String(kfp.state || "UNKNOWN").toUpperCase() : "UNAVAILABLE");
  const proofReady = runReady === true && modelReady === true && grafanaReady === true;
  const proofKnown = runReady !== null || modelReady !== null || grafanaReady !== null;
  const proofLabel = mlflow.status === "ready"
    ? `${String(run.status || "UNKNOWN").toUpperCase()} · ${model.alias ? `@${model.alias}` : "NO MODEL"} · GRAFANA ${grafanaReady ? "READY" : "CHECK"}`
    : "UNAVAILABLE";
  evidencePipelineStatus("evidence-run-state", proofKnown ? proofReady : null, proofLabel);

  byId("evidence-mae").textContent = finiteNumber(run.mae) === null ? "MAE —" : `MAE ${Number(run.mae).toFixed(2)}`;
  byId("evidence-alias").textContent = model.alias ? `@${model.alias} · v${model.version}` : "—";
  byId("evidence-duration").textContent = finiteNumber(kfp.durationSeconds) === null ? "—" : `${Number(kfp.durationSeconds)} sec`;

  const updated = byId("evidence-updated");
  const dot = document.createElement("span");
  dot.className = "live-dot";
  updated.replaceChildren(dot, document.createTextNode(evidence.generatedAt ? `${formatDate(evidence.generatedAt)} 검증` : "신호 없음"));

  const kfpOrigin = serviceOrigin("kubeflow-pipelines.192.168.0.56.nip.io", "kubeflow-pipelines.10.254.192.217.nip.io");
  const mlflowOrigin = serviceOrigin("mlflow.192.168.0.56.nip.io", "mlflow.10.254.192.217.nip.io");
  byId("evidence-kfp-link").href = kfp.runId ? `${kfpOrigin}/#/runs/details/${encodeURIComponent(kfp.runId)}` : kfpOrigin;
  byId("evidence-run-link").href = mlflow.experimentId && run.runId ? `${mlflowOrigin}/#/experiments/${encodeURIComponent(mlflow.experimentId)}/runs/${encodeURIComponent(run.runId)}` : mlflowOrigin;
  const proofLink = document.querySelector(".evidence-facts > a");
  proofLink.href = byId("evidence-run-link").href;
}

function proofStatus(elementId, ready, readyText, fallbackText = "확인 불가") {
  const element = byId(elementId);
  element.textContent = ready === true ? readyText : ready === false ? "DEGRADED" : fallbackText;
  element.closest("li, article").dataset.status = ready === true ? "ready" : ready === false ? "degraded" : "unknown";
}

function renderGpuTelemetry() {
  const target = byId("gpu-telemetry");
  const devices = state.operations?.gpu?.devices || [];
  const health = byId("gpu-health");
  if (!devices.length) {
    health.textContent = "NO SIGNAL";
    health.className = "status-pill neutral";
    target.innerHTML = '<p class="notice">DCGM 또는 HAMi에서 물리 GPU 정보를 가져오지 못했습니다.</p>';
    return;
  }
  const healthy = devices.filter((device) => device.health === true).length;
  health.textContent = `${healthy}/${devices.length} LIVE`;
  health.className = `status-pill ${healthy === devices.length ? "succeeded" : "pending"}`;
  target.innerHTML = devices.map((device) => {
    const used = finiteNumber(device.memoryUsedMiB);
    const total = finiteNumber(device.memoryTotalMiB);
    const memoryPercent = used !== null && total ? Math.max(0, Math.min(100, used / total * 100)) : 0;
    const logical = device.logicalAllocation || {};
    return `
      <article class="gpu-instrument-card">
        <header class="gpu-card-head"><div><small>${escapeHtml(publicIdentifier(device.node, "UNKNOWN NODE"))}</small><strong>${escapeHtml(device.model || "NVIDIA GPU")}</strong><code>${escapeHtml(shortUuid(device.uuid))}</code></div><span>${device.health === true ? "HEALTHY" : "CHECK"}</span></header>
        <div class="gpu-signal">
          <div><small>GPU UTIL</small><strong>${escapeHtml(fixedMetric(device.utilizationPercent, 0, "%"))}</strong></div>
          <div><small>TEMP</small><strong>${escapeHtml(fixedMetric(device.temperatureC, 0, "°C"))}</strong></div>
          <div><small>POWER</small><strong>${escapeHtml(fixedMetric(device.powerWatts, 1, "W"))}</strong></div>
        </div>
        <div class="gpu-meter"><div class="gpu-meter-label"><span>Physical framebuffer</span><span>${used === null || total === null ? "—" : `${used.toLocaleString()} / ${total.toLocaleString()} MiB`}</span></div><progress class="gpu-meter-track" max="100" value="${memoryPercent.toFixed(1)}">${memoryPercent.toFixed(1)}%</progress></div>
        <div class="gpu-logical"><span>HAMi logical allocation</span><strong>${escapeHtml(logical.workloadCount || 0)} workload · ${escapeHtml(logical.memoryMiB || 0)} MiB · ${escapeHtml(logical.corePercent || 0)}%</strong></div>
      </article>`;
  }).join("");
}

function renderOperations() {
  const operations = state.operations;
  if (!operations) {
    byId("operations-age").textContent = "신호 없음";
    byId("fleet-health").textContent = "UNAVAILABLE";
    byId("fleet-strip").innerHTML = '<p class="notice">운영 데이터를 불러오지 못했습니다.</p>';
    proofStatus("proof-api", null, "UNAVAILABLE");
    proofStatus("proof-queue", null, "UNAVAILABLE");
    proofStatus("proof-gpu", null, "UNAVAILABLE");
    byId("platform-components").innerHTML = '<p class="notice">구성요소 상태를 확인할 수 없습니다.</p>';
    byId("queue-instrument").innerHTML = '<p class="notice">Queue 상태를 확인할 수 없습니다.</p>';
    renderMlopsEvidence();
    renderGpuTelemetry();
    return;
  }
  const fleet = operations.fleet || {};
  const nodes = (operations.topology?.sites || []).flatMap((site) => site.nodes || []);
  byId("operations-age").textContent = `${formatDate(operations.generatedAt)} 수집`;
  byId("operations-ready").textContent = `${fleet.readyNodeCount ?? "—"}/${fleet.nodeCount ?? "—"}`;
  byId("fleet-health").textContent = fleet.readyNodeCount === fleet.nodeCount ? "ALL SYSTEMS NOMINAL" : "ATTENTION REQUIRED";
  byId("fleet-cpu").textContent = `${fixedMetric(fleet.cpuCores, 0)} cores`;
  byId("fleet-memory").textContent = `${fixedMetric(fleet.memoryGiB, 1)} GiB`;
  byId("fleet-gpu").textContent = `${fleet.physicalGpuCount ?? "—"} devices`;
  byId("fleet-arch").textContent = Object.entries(fleet.architectures || {}).map(([name, count]) => `${name}×${count}`).join(" · ") || "—";
  byId("fleet-pressure").textContent = `${fixedMetric(fleet.averageCpuPercent, 1, "%")} · ${fixedMetric(fleet.averageMemoryPercent, 1, "%")}`;
  byId("fleet-strip").innerHTML = nodes.map((node) => `<article class="fleet-node ${node.accelerator ? "gpu" : ""}" title="${escapeHtml(publicIdentifier(node.node))}"><small>${escapeHtml(node.executionClass)} · ${escapeHtml(node.architecture)}</small><strong>${escapeHtml(compactNodeName(node.node))}</strong></article>`).join("");

  const apiComponent = componentByName("Science API");
  proofStatus("proof-api", apiComponent ? apiComponent.status === "ready" : null, `${apiComponent?.ready}/${apiComponent?.desired} READY`);
  proofStatus("proof-queue", operations.queue?.status === "ready" ? true : operations.queue?.status === "degraded" ? false : null, `${operations.queue?.pendingWorkloads || 0} PENDING`);
  proofStatus("proof-gpu", operations.gpu?.deviceCount ? operations.gpu.healthyDeviceCount === operations.gpu.deviceCount : null, `${operations.gpu?.healthyDeviceCount}/${operations.gpu?.deviceCount} HEALTHY`);

  const platform = operations.platform || {};
  byId("platform-health").textContent = `${platform.readyCount ?? "—"}/${platform.componentCount ?? "—"} READY`;
  byId("platform-health").className = `status-pill ${platform.readyCount === platform.componentCount ? "succeeded" : "pending"}`;
  byId("platform-components").innerHTML = (platform.components || []).map((component) => `
    <div class="component-row"><span class="component-light ${escapeHtml(component.status)}"></span><div><strong>${escapeHtml(component.name)}</strong><small>${escapeHtml(publicIdentifier(component.namespace))} / ${escapeHtml(publicIdentifier(component.workload))}</small></div><span>${component.ready ?? "—"}/${component.desired ?? "—"}</span></div>`).join("");

  const queue = operations.queue || {};
  byId("queue-health").textContent = String(queue.status || "unknown").toUpperCase();
  byId("queue-health").className = `status-pill ${queue.status === "ready" ? "succeeded" : queue.status === "degraded" ? "pending" : "neutral"}`;
  byId("queue-instrument").innerHTML = `<div class="queue-primary"><small>CLUSTER QUEUE</small><strong>${escapeHtml(queue.name || "—")}</strong><span>${queue.status === "ready" ? "새 Workload 입장 가능" : "상태 확인 필요"}</span></div><div class="queue-counts"><div><small>PENDING</small><strong>${escapeHtml(queue.pendingWorkloads ?? "—")}</strong></div><div><small>FINISHED</small><strong>${escapeHtml(queue.finishedWorkloads ?? "—")}</strong></div></div>`;
  renderMlopsEvidence();
  renderGpuTelemetry();
}

function shortUuid(value) {
  const text = String(value || "");
  return text ? `${text.slice(0, 12)}…${text.slice(-6)}` : "배정 대기";
}

function topologyWorkload(workload, node) {
  const allocations = workload.allocations || [];
  const allocation = allocations[0] || {};
  const isTenant = workload.tenant && workload.tenant === state.config?.tenant;
  const stateName = workload.active ? statusLabel(String(workload.phase || "running").toLowerCase()) : "반환됨";
  return `
    <article class="gpu-allocation ${workload.active ? "active" : "released"}">
      <div class="allocation-status"><span class="status-dot"></span><span class="status-pill ${statusClass(workload.phase)}">${escapeHtml(stateName)}</span></div>
      <div class="allocation-workload"><small>${escapeHtml(isTenant ? "SCIENCE JOB" : `${publicIdentifier(workload.namespace, "shared")} · SHARED`)}</small><strong>${escapeHtml(publicIdentifier(workload.workload))}</strong><code>${escapeHtml(publicIdentifier(workload.pod))}</code></div>
      <div class="allocation-device"><small>${escapeHtml(allocation.model || node.accelerator?.model || "NVIDIA GPU")}</small><strong>${escapeHtml(shortUuid(allocation.uuid))}</strong><span>${escapeHtml(allocation.memoryMiB || workload.request?.memoryMiB || 0)} MiB · Core ${escapeHtml(allocation.corePercent || workload.request?.corePercent || 0)}%</span></div>
    </article>`;
}

function topologyNode(node) {
  const gpu = node.accelerator;
  const workloads = node.gpuWorkloads || [];
  const active = workloads.filter((item) => item.active).length;
  const pressure = node.pressure || {};
  const nodeClass = gpu ? "gpu-node" : "compute-node";
  const allocations = workloads.length
    ? workloads.map((workload) => topologyWorkload(workload, node)).join("")
    : `<div class="allocation-empty"><span>◇</span><div><strong>${gpu ? "배정된 GPU 작업 없음" : "GPU 비등록 노드"}</strong><small>${gpu ? "새 작업을 받을 수 있습니다." : "CPU 또는 Edge 실행에 사용됩니다."}</small></div></div>`;
  return `
    <article class="topology-node ${nodeClass}">
      <header class="node-heading">
        <div><span class="node-health ${node.health === "ready" ? "ready" : "not-ready"}"></span><div><small>${escapeHtml(node.executionClass)} · ${escapeHtml(node.architecture)}</small><h3>${escapeHtml(publicIdentifier(node.node))}</h3></div></div>
        <span class="status-pill ${node.health === "ready" ? "succeeded" : "failed"}">${escapeHtml(node.health)}</span>
      </header>
      <div class="node-facts">
        <div><small>CPU</small><strong>${escapeHtml(node.allocatable?.cpu || "—")}</strong></div>
        <div><small>Memory</small><strong>${escapeHtml(node.allocatable?.memory || "—")}</strong></div>
        <div><small>GPU</small><strong>${escapeHtml(gpu?.model || "—")}</strong></div>
        <div><small>Active</small><strong>${active}</strong></div>
      </div>
      ${gpu ? `<div class="gpu-slot"><div><small>PHYSICAL DEVICE</small><strong>${escapeHtml(gpu.model || "NVIDIA GPU")}</strong></div><div><small>Memory · Mode</small><strong>${escapeHtml(gpu.totalMemoryMiB || "—")} MiB · ${escapeHtml(gpu.mode || "—")}</strong></div></div>` : ""}
      <div class="node-pressure" aria-label="노드 관찰값"><span>CPU ${Number.isFinite(pressure.compute) ? `${pressure.compute.toFixed(1)}%` : "—"}</span><span>Memory ${Number.isFinite(pressure.memory) ? `${pressure.memory.toFixed(1)}%` : "—"}</span><span>Network ${Number.isFinite(pressure.network) ? `${pressure.network.toFixed(2)} MiB/s` : "—"}</span></div>
      <div class="allocation-list">${allocations}</div>
    </article>`;
}

function renderTopology() {
  const target = byId("topology-content");
  if (!state.topology) {
    byId("topology-health-label").textContent = "연결 실패";
    target.innerHTML = '<p class="notice topology-error">Resource Catalog에서 토폴로지를 가져오지 못했습니다. 새로고침 후 다시 확인하세요.</p>';
    return;
  }
  byId("nav-gpu-count").textContent = String(state.topology.gpuNodeCount ?? "—");
  byId("topology-sites").textContent = String(state.topology.siteCount ?? "—");
  byId("topology-ready").textContent = `${state.topology.readyNodeCount ?? "—"}/${state.topology.nodeCount ?? "—"}`;
  byId("topology-gpu-nodes").textContent = String(state.topology.gpuNodeCount ?? "—");
  byId("topology-active").textContent = String(state.topology.activeGpuAllocationCount ?? "—");
  byId("topology-health-label").textContent = "Live";
  byId("topology-generated-at").textContent = formatDate(state.topology.generatedAt);
  target.innerHTML = (state.topology.sites || []).map((site) => `
    <section class="site-topology">
      <header class="site-heading"><div><span class="site-mark">S</span><div><small>SITE</small><h3>${escapeHtml(publicIdentifier(site.site))}</h3></div></div><span>${escapeHtml(site.readyNodeCount)}/${escapeHtml(site.nodeCount)} Ready</span></header>
      <div class="node-grid">${[...(site.nodes || [])].sort((left, right) => Number(Boolean(right.accelerator)) - Number(Boolean(left.accelerator))).map(topologyNode).join("")}</div>
    </section>`).join("") || '<div class="empty-state"><div class="empty-symbol">◇</div><h3>표시할 Node가 없습니다</h3></div>';
}

function filteredJobs() {
  const query = state.search.trim().toLowerCase();
  return state.jobs.filter((job) => {
    const effective = effectiveStatus(job);
    const matchesStatus = state.statusFilter === "all" || effective === state.statusFilter || (state.statusFilter === "pending" && effective === "submitted");
    const haystack = [job.jobId, job.name, job.project, job.experiment].join(" ").toLowerCase();
    return matchesStatus && (!query || haystack.includes(query));
  });
}

function renderJobs() {
  const jobs = filteredJobs();
  const body = byId("jobs-table-body");
  byId("jobs-empty").hidden = jobs.length > 0;
  body.innerHTML = jobs.map((job) => `
    <tr tabindex="0" data-job-id="${escapeHtml(job.jobId)}" aria-label="${escapeHtml(job.project || job.name)} 상세 열기">
      <td><span class="job-identity"><strong>${escapeHtml(job.name || job.jobId)}</strong><small><code>${escapeHtml(job.jobId)}</code> · ${escapeHtml(job.experiment || "—")}</small></span></td>
      <td><span class="status-pill ${effectiveStatus(job)}">${escapeHtml(statusLabel(effectiveStatus(job)))}</span></td>
      <td>${escapeHtml(displayValue(job.project, "—"))}</td>
      <td title="${escapeHtml(queueReason(job))}">${escapeHtml(displayValue(job.queue?.name, state.config?.localQueue || "—"))}</td>
      <td>${escapeHtml(kfpLabel(job.kubeflow?.state))}</td>
      <td>${escapeHtml(formatDate(job.createdAt))}</td>
      <td class="row-arrow" aria-hidden="true">›</td>
    </tr>`).join("");
  body.querySelectorAll("tr[data-job-id]").forEach((row) => {
    row.addEventListener("click", () => openDetail(row.dataset.jobId));
    row.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openDetail(row.dataset.jobId); } });
  });
}

function renderAll() {
  renderOperations();
  renderOverview();
  renderTopology();
  renderJobs();
}

async function refreshAll({ quiet = false } = {}) {
  if (state.refreshing || !state.config) return;
  state.refreshing = true;
  const button = byId("refresh-button");
  button.textContent = "↻";
  button.style.transform = "rotate(35deg)";
  const [jobsResult, operationsResult] = await Promise.allSettled([api("/v1/jobs"), api("/v1/operations")]);
  if (jobsResult.status === "fulfilled") state.jobs = jobsResult.value.jobs || [];
  else if (!quiet) toast(`작업 목록: ${jobsResult.reason.message}`, "error");
  state.operations = operationsResult.status === "fulfilled" ? operationsResult.value : null;
  state.topology = state.operations?.topology || null;
  state.resources = state.topology;
  if (operationsResult.status === "rejected" && !quiet) toast(`운영 데이터: ${operationsResult.reason.message}`, "error");
  renderAll();
  byId("last-updated").textContent = `${new Intl.DateTimeFormat("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(new Date())} 동기화`;
  button.style.transform = "";
  state.refreshing = false;
}

function switchView(name) {
  if (!['overview', 'topology', 'jobs', 'submit'].includes(name)) return;
  state.activeView = name;
  document.querySelectorAll(".view").forEach((view) => view.classList.toggle("active", view.id === `${name}-view`));
  document.querySelectorAll("[data-view]").forEach((button) => button.classList.toggle("active", button.dataset.view === name));
  const labels = { overview: ["WORKSPACE", "개요"], topology: ["LIVE INFRASTRUCTURE", "토폴로지"], jobs: ["EXECUTIONS", "작업"], submit: ["NEW EXECUTION", "새 작업"] };
  byId("page-eyebrow").textContent = labels[name][0];
  byId("page-title").textContent = labels[name][1];
  window.scrollTo({ top: 0, behavior: "smooth" });
  byId("main-content").focus({ preventScroll: true });
}

async function openDetail(jobId) {
  state.selectedJobId = jobId;
  byId("detail-title").textContent = `science-${jobId}`;
  byId("detail-body").innerHTML = '<div class="detail-loading">작업 실행 경로를 불러오는 중…</div>';
  byId("cancel-job-button").hidden = true;
  if (!dialog.open) dialog.showModal();
  const [jobResult, metricsResult, artifactsResult] = await Promise.allSettled([
    api(`/v1/jobs/${encodeURIComponent(jobId)}`),
    api(`/v1/jobs/${encodeURIComponent(jobId)}/metrics`),
    api(`/v1/jobs/${encodeURIComponent(jobId)}/artifacts`),
  ]);
  if (state.selectedJobId !== jobId) return;
  if (jobResult.status === "rejected") {
    byId("detail-body").innerHTML = `<p class="form-error">${escapeHtml(jobResult.reason.message)}</p>`;
    return;
  }
  const job = jobResult.value;
  const metrics = metricsResult.status === "fulfilled" ? metricsResult.value : { error: metricsResult.reason.message };
  const artifacts = artifactsResult.status === "fulfilled" ? artifactsResult.value : { error: artifactsResult.reason.message };
  const request = job.request || {};
  const resources = request.resources || {};
  const placement = job.placement;
  const actualGpu = placement?.allocations?.[0] || {};
  const placementSection = resources.gpuCount ? `
    <section class="detail-section"><h3>실제 GPU 배정</h3>
      ${placement ? `<div class="placement-trace">
        <div><small>REQUEST</small><strong>${escapeHtml(resources.gpuMemoryMiB || "—")} MiB · ${escapeHtml(resources.gpuCorePercent || "—")}%</strong></div><i>→</i>
        <div><small>QUEUE</small><strong>${escapeHtml(job.queue?.name || state.config?.localQueue || "—")}</strong></div><i>→</i>
        <div><small>NODE</small><strong>${escapeHtml(publicIdentifier(placement.node))}</strong></div><i>→</i>
        <div class="placement-gpu"><small>${escapeHtml(placement.gpuModel || "NVIDIA GPU")}</small><strong>${escapeHtml(shortUuid(actualGpu.uuid))}</strong></div>
      </div><div class="placement-proof"><span class="status-pill ${placement.active ? "running" : "neutral"}">${placement.active ? "사용 중" : "반환됨"}</span><code>${escapeHtml(actualGpu.uuid || "GPU UUID 확인 대기")}</code><span>${escapeHtml(actualGpu.memoryMiB || resources.gpuMemoryMiB || "—")} MiB · Core ${escapeHtml(actualGpu.corePercent || resources.gpuCorePercent || "—")}%</span></div>` : '<p class="notice">아직 Scheduler가 GPU를 배정하지 않았거나 보존 기간이 지나 Pod 기록이 정리되었습니다.</p>'}
    </section>` : "";
  byId("detail-body").innerHTML = `
    <section class="detail-hero"><div><strong>${escapeHtml(job.project || job.name)}</strong><code>${escapeHtml(job.jobId)}</code></div><span class="status-pill ${effectiveStatus(job)}">${escapeHtml(statusLabel(effectiveStatus(job)))}</span></section>
    <section class="detail-section"><h3>실행 상태</h3><div class="detail-grid">
      <div class="detail-cell"><small>Experiment</small><strong>${escapeHtml(displayValue(job.experiment))}</strong></div>
      <div class="detail-cell"><small>Kubeflow</small><strong>${escapeHtml(kfpLabel(job.kubeflow?.state))}</strong></div>
      <div class="detail-cell"><small>LocalQueue</small><strong>${escapeHtml(displayValue(job.queue?.name, state.config?.localQueue))}</strong></div>
      <div class="detail-cell"><small>Queue 판단</small><strong>${escapeHtml(queueReason(job))}</strong></div>
      <div class="detail-cell"><small>CPU / Memory</small><strong>${escapeHtml(`${displayValue(resources.cpu, "—")} / ${displayValue(resources.memory, "—")}`)}</strong></div>
      <div class="detail-cell"><small>GPU</small><strong>${escapeHtml(resources.gpuCount ? `${resources.gpuCount} · ${resources.gpuMemoryMiB || "—"} MiB · ${resources.gpuCorePercent || "—"}%` : "사용 안 함")}</strong></div>
      <div class="detail-cell"><small>Dataset</small><strong>${escapeHtml(displayValue(request.datasetVersion))}</strong></div>
      <div class="detail-cell"><small>생성 시각</small><strong>${escapeHtml(formatDate(job.createdAt))}</strong></div>
    </div></section>
    ${placementSection}
    <section class="detail-section"><h3>Metric과 Parameter</h3><pre class="json-block">${jsonText(metrics)}</pre></section>
    <section class="detail-section"><h3>Artifact</h3><pre class="json-block">${jsonText(artifacts)}</pre></section>`;
  byId("cancel-job-button").hidden = ["succeeded", "failed"].includes(effectiveStatus(job));
}

function formPayload() {
  const values = new FormData(jobForm);
  const command = String(values.get("command") || "").split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
  const resources = { cpu: String(values.get("cpu") || ""), memory: String(values.get("memory") || "") };
  if (byId("gpu-toggle").checked) {
    resources.acceleratorVendor = "nvidia";
    resources.gpuCount = Number(values.get("gpuCount"));
    resources.gpuMemoryMiB = Number(values.get("gpuMemoryMiB"));
    resources.gpuCorePercent = Number(values.get("gpuCorePercent"));
  }
  return {
    project: String(values.get("project") || ""), image: String(values.get("image") || ""), command, resources,
    datasetVersion: String(values.get("datasetVersion") || ""), experiment: String(values.get("experiment") || ""),
    priority: String(values.get("priority") || "normal"), gitCommit: String(values.get("gitCommit") || "unknown"),
  };
}

document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
document.querySelectorAll('[data-action="go-submit"]').forEach((button) => button.addEventListener("click", () => switchView("submit")));
document.querySelectorAll('[data-action="go-jobs"]').forEach((button) => button.addEventListener("click", () => switchView("jobs")));
document.querySelectorAll('[data-action="close-dialog"]').forEach((button) => button.addEventListener("click", () => dialog.close()));
byId("new-job-button").addEventListener("click", () => switchView("submit"));
byId("retry-connection").addEventListener("click", () => reconnectPortal());
byId("reconnect-button").addEventListener("click", async () => {
  await fetch("/v1/portal/session", { method: "DELETE", credentials: "same-origin" });
  await reconnectPortal();
});
byId("refresh-button").addEventListener("click", () => refreshAll());
byId("gpu-toggle").addEventListener("change", (event) => { byId("gpu-fields").hidden = !event.target.checked; });
byId("job-search").addEventListener("input", (event) => { state.search = event.target.value; renderJobs(); });
byId("status-filters").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-status]");
  if (!button) return;
  state.statusFilter = button.dataset.status;
  byId("status-filters").querySelectorAll("button").forEach((item) => item.classList.toggle("active", item === button));
  renderJobs();
});

jobForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const error = byId("submit-error");
  error.hidden = true;
  if (!jobForm.reportValidity()) return;
  const payload = formPayload();
  if (!payload.command.length) { error.textContent = "Command 인자를 한 개 이상 입력하세요."; error.hidden = false; return; }
  const button = byId("submit-button");
  setBusy(button, true, "Kueue와 Kubeflow에 제출 중…");
  try {
    const result = await api("/v1/jobs", { method: "POST", body: JSON.stringify(payload) });
    toast(`Job ${result.jobId}가 제출되었습니다.`);
    await refreshAll({ quiet: true });
    switchView("jobs");
    await openDetail(result.jobId);
  } catch (reason) {
    error.textContent = reason.message;
    error.hidden = false;
    error.scrollIntoView({ behavior: "smooth", block: "center" });
  } finally { setBusy(button, false); }
});

byId("cancel-job-button").addEventListener("click", async () => {
  const jobId = state.selectedJobId;
  if (!jobId || !window.confirm(`science-${jobId} 작업을 취소하시겠습니까? 이 작업의 Kubeflow Run도 종료됩니다.`)) return;
  const button = byId("cancel-job-button");
  setBusy(button, true, "취소 중…");
  try { await api(`/v1/jobs/${encodeURIComponent(jobId)}`, { method: "DELETE" }); dialog.close(); toast(`Job ${jobId}를 취소했습니다.`); await refreshAll(); }
  catch (reason) { toast(reason.message, "error"); }
  finally { setBusy(button, false); }
});

dialog.addEventListener("click", (event) => {
  const rect = dialog.getBoundingClientRect();
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
});
dialog.addEventListener("close", () => { state.selectedJobId = null; });
document.addEventListener("visibilitychange", () => { if (!document.hidden && state.config) refreshAll({ quiet: true }); });
window.setInterval(() => { if (!document.hidden && state.config) refreshAll({ quiet: true }); }, 8000);

function rewriteInstitutionLinks() {
  if (!location.hostname.endsWith(".10.254.192.217.nip.io")) return;
  document.querySelectorAll("a[href]").forEach((link) => {
    link.href = link.href
      .replace("research-hub.192.168.0.56.nip.io", "research-hub.10.254.192.217.nip.io")
      .replace("mini-science-ai-os.192.168.0.56.nip.io", "mini-science-ai-os.10.254.192.217.nip.io")
      .replace("kubeflow-pipelines.192.168.0.56.nip.io", "kubeflow-pipelines.10.254.192.217.nip.io")
      .replace("mlflow.192.168.0.56.nip.io", "mlflow.10.254.192.217.nip.io")
      .replace("grafana.192.168.0.56.sslip.io", "grafana.10.254.192.217.nip.io");
  });
}

(async function boot() {
  rewriteInstitutionLinks();
  await reconnectPortal();
})();
