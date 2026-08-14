from __future__ import annotations

import os
from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar

import httpx2
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from prometheus_client import Counter, make_asgi_app
from starlette.requests import Request
from starlette.responses import JSONResponse

from .common import AuditLogger, sanitize


TENANT = os.getenv("TENANT", "etri")
API_URL = os.getenv("SCIENCE_JOB_API_URL", f"http://science-job-api.{os.getenv('TENANT_NAMESPACE', 'tenant-etri')}.svc.cluster.local:8000").rstrip("/")
API_TOKEN = os.getenv("TENANT_API_TOKEN", "")
CATALOG_URL = os.getenv("RESOURCE_CATALOG_URL", "http://resource-catalog.science-ai-system.svc.cluster.local:8000").rstrip("/")
PLATFORM_VERSION = os.getenv("PLATFORM_VERSION", "0.3.1")

TOOL_CALLS = Counter("science_mcp_tool_calls_total", "MCP tool calls", ["tool", "result"])
AUDIT = AuditLogger("tenant-mcp-server")

mcp = MCPServer(
    name=f"mini-science-ai-os-{TENANT}-mcp",
    version=PLATFORM_VERSION,
    instructions="Tenant-scoped Science Job tools. This server never calls the Kubernetes API directly.",
)


async def _request(base_url: str, method: str, path: str, **kwargs: Any) -> Any:
    headers = dict(kwargs.pop("headers", {}))
    headers["X-Science-Token"] = API_TOKEN
    headers["X-Science-Tenant"] = TENANT
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    async with httpx2.AsyncClient(timeout=10.0) as http:
        response = await http.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()


async def _api(method: str, path: str, **kwargs: Any) -> Any:
    return await _request(API_URL, method, path, **kwargs)


async def _catalog(path: str) -> Any:
    return await _request(CATALOG_URL, "GET", path, headers={})


T = TypeVar("T")


def audited(name: str) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    def decorator(handler: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(handler)
        async def wrapped(*args: Any, **kwargs: Any) -> T:
            arguments = {"args": sanitize(args), "kwargs": sanitize(kwargs)}
            job_id = kwargs.get("job_id")
            if job_id is None and name in {"get_job_status", "get_run_metrics", "cancel_own_job"} and args:
                job_id = str(args[0])
            try:
                result = await handler(*args, **kwargs)
                if job_id is None and isinstance(result, dict):
                    job_id = result.get("jobId")
                TOOL_CALLS.labels(name, "success").inc()
                AUDIT.emit(tenant=TENANT, tool_name=name, arguments=arguments, authorization_decision="allow", linked_job_id=job_id, result=result)
                return result
            except Exception as exc:
                TOOL_CALLS.labels(name, "error").inc()
                AUDIT.emit(tenant=TENANT, tool_name=name, arguments=arguments, authorization_decision="allow", linked_job_id=job_id, error=type(exc).__name__)
                raise

        return wrapped

    return decorator


@mcp.tool()
@audited("list_available_resources")
async def list_available_resources() -> dict[str, Any]:
    return await _catalog("/v1/resources/summary")


@mcp.tool()
@audited("submit_science_job")
async def submit_science_job(job: dict[str, Any]) -> dict[str, Any]:
    return await _api("POST", "/v1/jobs", json=job)


@mcp.tool()
@audited("get_job_status")
async def get_job_status(job_id: str) -> dict[str, Any]:
    return await _api("GET", f"/v1/jobs/{job_id}")


@mcp.tool()
@audited("get_run_metrics")
async def get_run_metrics(job_id: str) -> dict[str, Any]:
    return await _api("GET", f"/v1/jobs/{job_id}/metrics")


@mcp.tool()
@audited("list_experiment_runs")
async def list_experiment_runs(experiment: str) -> dict[str, Any]:
    return await _api("GET", f"/v1/experiments/{experiment}/runs")


@mcp.tool()
@audited("cancel_own_job")
async def cancel_own_job(job_id: str) -> dict[str, Any]:
    return await _api("DELETE", f"/v1/jobs/{job_id}")


@mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
async def healthz(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "tenant": TENANT, "version": PLATFORM_VERSION})


_allowed_hosts = [item.strip() for item in os.getenv("MCP_ALLOWED_HOSTS", "localhost,127.0.0.1,mcp-agent-runtime").split(",") if item.strip()]
app = mcp.streamable_http_app(
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
    host="0.0.0.0",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=_allowed_hosts),
)
app.mount("/metrics", make_asgi_app())
