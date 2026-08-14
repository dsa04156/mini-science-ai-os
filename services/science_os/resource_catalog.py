from __future__ import annotations

import json
import os
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
