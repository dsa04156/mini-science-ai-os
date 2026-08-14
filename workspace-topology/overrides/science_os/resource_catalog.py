from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import UTC, datetime
from typing import Any

import httpx2
from fastapi import FastAPI
from kubernetes.client import CoreV1Api, CustomObjectsApi
from prometheus_client import Counter, make_asgi_app

from .common import load_kubernetes_clients, parse_memory_bytes


CATALOG_REQUESTS = Counter("science_catalog_requests_total", "Resource Catalog requests", ["route"])
PROMETHEUS_ERRORS = Counter("science_catalog_prometheus_errors_total", "Prometheus query errors")


app = FastAPI(title="mini-science-ai-os Resource Catalog", version="0.1.0")
app.mount("/metrics", make_asgi_app())


def _kube() -> tuple[CoreV1Api, CustomObjectsApi]:
    core, _, custom = load_kubernetes_clients()
    return core, custom


def _hami_devices(node: Any) -> list[dict[str, Any]]:
    raw = (node.metadata.annotations or {}).get("hami.io/node-nvidia-register", "[]")
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    return value if isinstance(value, list) else []


def _node_accelerator(node: Any, allocated_memory: int | None) -> dict[str, Any] | None:
    devices = _hami_devices(node)
    if not devices and not (node.status.allocatable or {}).get("nvidia.com/gpu"):
        return None
    first = devices[0] if devices else {}
    return {
        "vendor": "nvidia",
        "model": first.get("type"),
        "mode": first.get("mode", "unknown"),
        "totalMemoryMiB": first.get("devmem"),
        "allocatedMemoryMiB": allocated_memory,
        "virtualDeviceCount": first.get("count"),
        "health": first.get("health"),
    }


def _node_devices(node: Any) -> list[dict[str, Any]]:
    return [
        {
            "uuid": device.get("id"),
            "model": device.get("type"),
            "mode": device.get("mode", "unknown"),
            "memoryMiB": device.get("devmem"),
            "corePercent": device.get("devcore"),
            "virtualDeviceCount": device.get("count"),
            "health": device.get("health"),
        }
        for device in _hami_devices(node)
    ]


def _execution_class(node: Any) -> str:
    labels = node.metadata.labels or {}
    if labels.get("science-ai.io/execution-class"):
        return labels["science-ai.io/execution-class"]
    if labels.get("environment") == "edge":
        return "edge"
    if labels.get("gpu") == "on" or labels.get("gpu.platform"):
        return "gpu"
    return "compute"


async def _query_prometheus(query: str) -> float | None:
    base = os.getenv("PROMETHEUS_URL", "http://prometheus-kube-prometheus-prometheus.kube-system.svc.cluster.local:9090").rstrip("/")
    try:
        async with httpx2.AsyncClient(timeout=3.0) as http:
            response = await http.get(f"{base}/api/v1/query", params={"query": query})
            response.raise_for_status()
            payload = response.json()
            results = payload.get("data", {}).get("result", [])
            if not results:
                return None
            return float(results[0].get("value", [None, None])[1])
    except (httpx2.HTTPError, ValueError, TypeError, KeyError):
        PROMETHEUS_ERRORS.inc()
        return None


async def _query_prometheus_vector(query: str) -> list[dict[str, Any]]:
    base = os.getenv("PROMETHEUS_URL", "http://prometheus-kube-prometheus-prometheus.kube-system.svc.cluster.local:9090").rstrip("/")
    try:
        async with httpx2.AsyncClient(timeout=3.0) as http:
            response = await http.get(f"{base}/api/v1/query", params={"query": query})
            response.raise_for_status()
            payload = response.json()
            results = payload.get("data", {}).get("result", [])
            return results if isinstance(results, list) else []
    except (httpx2.HTTPError, ValueError, TypeError, KeyError):
        PROMETHEUS_ERRORS.inc()
        return []


def _metric_value(item: dict[str, Any]) -> float | None:
    try:
        return float(item.get("value", [None, None])[1])
    except (TypeError, ValueError, IndexError):
        return None


def _cpu_cores(value: Any) -> float:
    text = str(value or "0")
    try:
        return float(text[:-1]) / 1000 if text.endswith("m") else float(text)
    except ValueError:
        return 0.0


def _fleet_summary(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    architectures: dict[str, int] = {}
    execution_classes: dict[str, int] = {}
    for node in nodes:
        architecture = str(node.get("architecture") or "unknown")
        execution_class = str(node.get("executionClass") or "unknown")
        architectures[architecture] = architectures.get(architecture, 0) + 1
        execution_classes[execution_class] = execution_classes.get(execution_class, 0) + 1
    compute_values = [node.get("pressure", {}).get("compute") for node in nodes]
    memory_values = [node.get("pressure", {}).get("memory") for node in nodes]
    compute_samples = [float(value) for value in compute_values if isinstance(value, (int, float))]
    memory_samples = [float(value) for value in memory_values if isinstance(value, (int, float))]
    return {
        "nodeCount": len(nodes),
        "readyNodeCount": sum(node.get("health") == "ready" for node in nodes),
        "gpuNodeCount": sum(bool(node.get("accelerator")) for node in nodes),
        "physicalGpuCount": sum(len(node.get("gpuDevices", [])) for node in nodes),
        "cpuCores": round(sum(_cpu_cores(node.get("allocatable", {}).get("cpu")) for node in nodes), 1),
        "memoryGiB": round(sum(parse_memory_bytes(str(node.get("allocatable", {}).get("memory") or "0")) for node in nodes) / 1024**3, 1),
        "architectures": architectures,
        "executionClasses": execution_classes,
        "averageCpuPercent": round(sum(compute_samples) / len(compute_samples), 1) if compute_samples else None,
        "averageMemoryPercent": round(sum(memory_samples) / len(memory_samples), 1) if memory_samples else None,
    }


async def _gpu_telemetry(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metric_names = {
        "utilizationPercent": "DCGM_FI_DEV_GPU_UTIL",
        "memoryUsedMiB": "DCGM_FI_DEV_FB_USED",
        "temperatureC": "DCGM_FI_DEV_GPU_TEMP",
        "powerWatts": "DCGM_FI_DEV_POWER_USAGE",
    }
    metric_results = await asyncio.gather(*(_query_prometheus_vector(name) for name in metric_names.values()))
    values: dict[str, dict[str, Any]] = {}
    for field, results in zip(metric_names, metric_results, strict=True):
        for item in results:
            metric = item.get("metric", {})
            uuid = metric.get("UUID")
            if not uuid:
                continue
            values.setdefault(uuid, {})[field] = _metric_value(item)
            values[uuid]["driverVersion"] = metric.get("DCGM_FI_DRIVER_VERSION")
            values[uuid]["model"] = metric.get("modelName")

    telemetry: list[dict[str, Any]] = []
    for node in nodes:
        active_workloads = [item for item in node.get("gpuWorkloads", []) if item.get("active")]
        logical_by_uuid: dict[str, dict[str, int]] = {}
        for workload in active_workloads:
            for allocation in workload.get("allocations", []):
                uuid = allocation.get("uuid")
                if not uuid:
                    continue
                logical = logical_by_uuid.setdefault(uuid, {"memoryMiB": 0, "corePercent": 0, "workloadCount": 0})
                logical["memoryMiB"] += int(allocation.get("memoryMiB") or 0)
                logical["corePercent"] += int(allocation.get("corePercent") or 0)
                logical["workloadCount"] += 1
        for device in node.get("gpuDevices", []):
            uuid = device.get("uuid")
            live = values.get(uuid, {})
            telemetry.append(
                {
                    "node": node.get("node"),
                    "uuid": uuid,
                    "model": live.get("model") or device.get("model"),
                    "driverVersion": live.get("driverVersion"),
                    "health": device.get("health"),
                    "memoryTotalMiB": device.get("memoryMiB"),
                    "utilizationPercent": live.get("utilizationPercent"),
                    "memoryUsedMiB": live.get("memoryUsedMiB"),
                    "temperatureC": live.get("temperatureC"),
                    "powerWatts": live.get("powerWatts"),
                    "logicalAllocation": logical_by_uuid.get(uuid, {"memoryMiB": 0, "corePercent": 0, "workloadCount": 0}),
                }
            )
    return telemetry


def _component_snapshot(available: list[dict[str, Any]], desired: list[dict[str, Any]], stateful: list[dict[str, Any]]) -> list[dict[str, Any]]:
    available_by_key = {
        (item.get("metric", {}).get("namespace"), item.get("metric", {}).get("deployment")): _metric_value(item)
        for item in available
    }
    desired_by_key = {
        (item.get("metric", {}).get("namespace"), item.get("metric", {}).get("deployment")): _metric_value(item)
        for item in desired
    }
    ready_stateful = {
        (item.get("metric", {}).get("namespace"), item.get("metric", {}).get("statefulset")): _metric_value(item)
        for item in stateful
    }
    targets = [
        ("Science API", "tenant-etri", "science-job-api", "deployment"),
        ("Agent Runtime", "tenant-etri", "agent-runtime", "deployment"),
        ("Resource Catalog", "science-ai-system", "resource-catalog", "deployment"),
        ("Kubeflow API", "kubeflow", "ml-pipeline", "deployment"),
        ("Metadata DB", "kubeflow", "mysql", "deployment"),
        ("Artifact Store", "science-ai-mlops", "minio", "statefulset"),
    ]
    components = []
    for label, namespace, name, kind in targets:
        key = (namespace, name)
        if kind == "statefulset":
            ready = ready_stateful.get(key)
            expected = 1.0
        else:
            ready = available_by_key.get(key)
            expected = desired_by_key.get(key)
        status = "ready" if ready is not None and expected is not None and ready >= expected and expected > 0 else "degraded" if ready is not None else "unknown"
        components.append(
            {
                "name": label,
                "namespace": namespace,
                "workload": name,
                "kind": kind,
                "ready": int(ready) if ready is not None else None,
                "desired": int(expected) if expected is not None else None,
                "status": status,
            }
        )
    return components


async def _platform_health() -> dict[str, Any]:
    available, desired, stateful = await asyncio.gather(
        _query_prometheus_vector("kube_deployment_status_replicas_available"),
        _query_prometheus_vector("kube_deployment_spec_replicas"),
        _query_prometheus_vector("kube_statefulset_status_replicas_ready"),
    )
    components = _component_snapshot(available, desired, stateful)
    return {
        "components": components,
        "readyCount": sum(item["status"] == "ready" for item in components),
        "componentCount": len(components),
    }


def _condition_true(item: dict[str, Any], condition_type: str) -> bool:
    return any(condition.get("type") == condition_type and condition.get("status") == "True" for condition in item.get("status", {}).get("conditions", []))


def _queue_health(custom: CustomObjectsApi) -> dict[str, Any]:
    queue_name = os.getenv("CLUSTER_QUEUE", "science-shared")
    try:
        payload = custom.list_cluster_custom_object("kueue.x-k8s.io", "v1beta1", "workloads")
        workloads = payload.get("items", [])
        queue = custom.get_cluster_custom_object("kueue.x-k8s.io", "v1beta1", "clusterqueues", queue_name)
        active = any(condition.get("type") == "Active" and condition.get("status") == "True" for condition in queue.get("status", {}).get("conditions", []))
        return {
            "name": queue_name,
            "status": "ready" if active else "degraded",
            "pendingWorkloads": int(queue.get("status", {}).get("pendingWorkloads") or 0),
            "admittedWorkloads": int(queue.get("status", {}).get("admittedWorkloads") or 0),
            "observedWorkloads": len(workloads),
            "finishedWorkloads": sum(_condition_true(item, "Finished") for item in workloads),
        }
    except Exception:
        return {
            "name": queue_name,
            "status": "unknown",
            "pendingWorkloads": None,
            "admittedWorkloads": None,
            "observedWorkloads": None,
            "finishedWorkloads": None,
        }


async def _pressures(node: Any) -> dict[str, float | None]:
    address = next((item.address for item in node.status.addresses or [] if item.type == "InternalIP"), None)
    if not address:
        return {"compute": None, "memory": None, "network": None}
    instance = f'{address}:9100'
    compute = await _query_prometheus(
        f'100 - (avg(rate(node_cpu_seconds_total{{instance="{instance}",mode="idle"}}[5m])) * 100)'
    )
    memory = await _query_prometheus(
        f'100 * (1 - (node_memory_MemAvailable_bytes{{instance="{instance}"}} / node_memory_MemTotal_bytes{{instance="{instance}"}}))'
    )
    network = await _query_prometheus(
        f'sum(rate(node_network_receive_bytes_total{{instance="{instance}",device!~"lo|cni.*|flannel.*"}}[5m])) / 1048576'
    )
    return {"compute": compute, "memory": memory, "network": network}


async def _allocated_memory(core: CoreV1Api, node_name: str) -> int | None:
    try:
        pods = core.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={node_name}").items
    except Exception:
        return None
    total = 0
    found = False
    resource_name = os.getenv("HAMI_MEMORY_RESOURCE", "nvidia.com/gpumem")
    for pod in pods:
        # Completed/failed Pods retain historical HAMI fields but no longer
        # consume a device, so count only live phases.
        if (pod.status.phase if pod.status else None) not in {"Pending", "Running"}:
            continue
        for container in pod.spec.containers or []:
            resources = container.resources or {}
            limits = resources.limits or {}
            requests = resources.requests or {}
            value = limits.get(resource_name) or requests.get(resource_name)
            if value is not None:
                found = True
                try:
                    total += int(str(value).rstrip("Mi"))
                except ValueError:
                    continue
    return total if found else 0


def _resource_int(value: Any) -> int:
    if value is None:
        return 0
    match = re.search(r"\d+", str(value))
    return int(match.group()) if match else 0


def _pod_gpu_request(pod: Any) -> dict[str, int]:
    names = {
        "count": os.getenv("HAMI_COUNT_RESOURCE", "nvidia.com/gpu"),
        "memoryMiB": os.getenv("HAMI_MEMORY_RESOURCE", "nvidia.com/gpumem"),
        "corePercent": os.getenv("HAMI_CORE_RESOURCE", "nvidia.com/gpucores"),
    }
    result = {"count": 0, "memoryMiB": 0, "corePercent": 0}
    for container in pod.spec.containers or []:
        resources = container.resources or {}
        limits = resources.limits or {}
        requests = resources.requests or {}
        for field, name in names.items():
            result[field] += _resource_int(limits.get(name) or requests.get(name))
    return result


def _parse_hami_allocations(raw: str | None, devices: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    allocations: list[dict[str, Any]] = []
    for match in re.finditer(r"(GPU-[^,;:]+),([^,;:]+),(\d+),(\d+)", raw or ""):
        uuid, vendor, memory, core = match.groups()
        device = devices.get(uuid, {})
        allocations.append(
            {
                "uuid": uuid,
                "vendor": vendor,
                "model": device.get("model"),
                "memoryMiB": int(memory),
                "corePercent": int(core),
            }
        )
    return allocations


def _gpu_workload(pod: Any, devices: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    annotations = pod.metadata.annotations or {}
    labels = pod.metadata.labels or {}
    request = _pod_gpu_request(pod)
    allocations = _parse_hami_allocations(annotations.get("hami.io/vgpu-devices-allocated"), devices)
    if not request["count"] and not allocations:
        return None
    phase = pod.status.phase if pod.status else "Unknown"
    owner = next((ref.name for ref in pod.metadata.owner_references or [] if ref.controller), None)
    job_id = labels.get("science-ai.io/job-id")
    if not allocations and request["count"]:
        allocations = [
            {
                "uuid": None,
                "vendor": "NVIDIA",
                "model": None,
                "memoryMiB": request["memoryMiB"],
                "corePercent": request["corePercent"],
            }
        ]
    return {
        "namespace": pod.metadata.namespace,
        "pod": pod.metadata.name,
        "workload": f"science-{job_id}" if job_id else labels.get("app.kubernetes.io/name") or owner or pod.metadata.name,
        "jobId": job_id,
        "project": labels.get("science-ai.io/project"),
        "experiment": labels.get("science-ai.io/experiment"),
        "tenant": labels.get("science-ai.io/tenant"),
        "phase": phase,
        "active": phase in {"Pending", "Running"},
        "node": pod.spec.node_name,
        "request": request,
        "allocations": allocations,
    }


async def observe_nodes() -> list[dict[str, Any]]:
    core, _ = _kube()
    nodes = core.list_node().items
    observed: list[dict[str, Any]] = []
    for node in nodes:
        labels = node.metadata.labels or {}
        allocatable = node.status.allocatable or {}
        memory = await _allocated_memory(core, node.metadata.name)
        pressure = await _pressures(node)
        ready = next((condition.status == "True" for condition in node.status.conditions or [] if condition.type == "Ready"), False)
        observed.append(
            {
                "site": labels.get("science-ai.io/site", os.getenv("DEFAULT_SITE", "etri-lab")),
                "node": node.metadata.name,
                "architecture": node.status.node_info.architecture if node.status.node_info else labels.get("kubernetes.io/arch"),
                "executionClass": _execution_class(node),
                "accelerator": _node_accelerator(node, memory),
                "gpuDevices": _node_devices(node),
                "allocatable": {
                    "cpu": allocatable.get("cpu"),
                    "memory": allocatable.get("memory"),
                    "gpu": allocatable.get(os.getenv("HAMI_COUNT_RESOURCE", "nvidia.com/gpu")),
                },
                "pressure": pressure,
                "health": "ready" if ready else "not-ready",
                "taints": [taint.to_dict() for taint in node.spec.taints or []],
            }
        )
    return observed


async def observe_topology() -> dict[str, Any]:
    core, _ = _kube()
    nodes = await observe_nodes()
    by_name = {node["node"]: node for node in nodes}
    devices = {
        device["uuid"]: device
        for node in nodes
        for device in node.get("gpuDevices", [])
        if device.get("uuid")
    }
    try:
        pods = core.list_pod_for_all_namespaces().items
    except Exception:
        pods = []
    allocations: list[dict[str, Any]] = []
    for pod in pods:
        workload = _gpu_workload(pod, devices)
        if not workload:
            continue
        allocations.append(workload)
        if workload.get("node") in by_name:
            by_name[workload["node"]].setdefault("gpuWorkloads", []).append(workload)
    for node in nodes:
        node.setdefault("gpuWorkloads", [])
        node["gpuWorkloads"].sort(key=lambda item: (not item["active"], item["namespace"], item["workload"]))
    sites = []
    for site_name in sorted({node["site"] for node in nodes}):
        site_nodes = [node for node in nodes if node["site"] == site_name]
        sites.append(
            {
                "site": site_name,
                "nodeCount": len(site_nodes),
                "readyNodeCount": sum(node["health"] == "ready" for node in site_nodes),
                "nodes": site_nodes,
            }
        )
    gpu_nodes = [node for node in nodes if node["accelerator"]]
    return {
        "generatedAt": datetime.now(UTC).isoformat(),
        "siteCount": len(sites),
        "nodeCount": len(nodes),
        "readyNodeCount": sum(node["health"] == "ready" for node in nodes),
        "gpuNodeCount": len(gpu_nodes),
        "activeGpuAllocationCount": sum(item["active"] for item in allocations),
        "gpuNodes": gpu_nodes,
        "sites": sites,
        "resourceNames": {
            "count": os.getenv("HAMI_COUNT_RESOURCE", "nvidia.com/gpu"),
            "memory": os.getenv("HAMI_MEMORY_RESOURCE", "nvidia.com/gpumem"),
            "core": os.getenv("HAMI_CORE_RESOURCE", "nvidia.com/gpucores"),
        },
    }


async def observe_operations() -> dict[str, Any]:
    topology_payload = await observe_topology()
    nodes = [node for site in topology_payload.get("sites", []) for node in site.get("nodes", [])]
    _, custom = _kube()
    gpu_devices, platform, queue = await asyncio.gather(
        _gpu_telemetry(nodes),
        _platform_health(),
        asyncio.to_thread(_queue_health, custom),
    )
    return {
        "generatedAt": datetime.now(UTC).isoformat(),
        "dataSources": ["Kubernetes", "Kueue", "HAMi", "Prometheus", "DCGM", "Kubeflow"],
        "fleet": _fleet_summary(nodes),
        "gpu": {
            "devices": gpu_devices,
            "healthyDeviceCount": sum(device.get("health") is True for device in gpu_devices),
            "deviceCount": len(gpu_devices),
        },
        "queue": queue,
        "platform": platform,
        "topology": topology_payload,
    }


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/sites")
async def sites() -> dict[str, Any]:
    CATALOG_REQUESTS.labels("sites").inc()
    nodes = await observe_nodes()
    sites = sorted({node["site"] for node in nodes})
    return {"sites": [{"site": site, "nodeCount": sum(node["site"] == site for node in nodes)} for site in sites]}


@app.get("/v1/nodes")
async def nodes() -> dict[str, Any]:
    CATALOG_REQUESTS.labels("nodes").inc()
    return {"nodes": await observe_nodes()}


@app.get("/v1/resources")
async def resources() -> dict[str, Any]:
    CATALOG_REQUESTS.labels("resources").inc()
    return {"resources": await observe_nodes()}


@app.get("/v1/resources/summary")
async def resources_summary() -> dict[str, Any]:
    CATALOG_REQUESTS.labels("summary").inc()
    nodes = await observe_nodes()
    gpu_nodes = [node for node in nodes if node["accelerator"]]
    return {
        "siteCount": len({node["site"] for node in nodes}),
        "nodeCount": len(nodes),
        "readyNodeCount": sum(node["health"] == "ready" for node in nodes),
        "gpuNodeCount": len(gpu_nodes),
        "gpuNodes": gpu_nodes,
        "resourceNames": {
            "count": os.getenv("HAMI_COUNT_RESOURCE", "nvidia.com/gpu"),
            "memory": os.getenv("HAMI_MEMORY_RESOURCE", "nvidia.com/gpumem"),
            "core": os.getenv("HAMI_CORE_RESOURCE", "nvidia.com/gpucores"),
        },
    }


@app.get("/v1/topology")
async def topology() -> dict[str, Any]:
    CATALOG_REQUESTS.labels("topology").inc()
    return await observe_topology()


@app.get("/v1/operations")
async def operations() -> dict[str, Any]:
    CATALOG_REQUESTS.labels("operations").inc()
    return await observe_operations()
