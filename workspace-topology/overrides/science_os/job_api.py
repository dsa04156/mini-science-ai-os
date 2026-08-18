from __future__ import annotations

import json
import os
import re
import secrets
import base64
import hashlib
import hmac
import time
import uuid
from pathlib import Path
from typing import Any, Literal

import httpx2
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from kfp import Client as KubeflowClient
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from prometheus_client import Counter, Histogram, make_asgi_app
from kubernetes import client

from .common import AuditLogger, env_bool, image_registry, load_kubernetes_clients, parse_cpu_milli, parse_memory_bytes
from .kfp_pipeline import science_job_pipeline


TENANT_NAMESPACE = os.getenv("TENANT_NAMESPACE", "tenant-etri")
TENANT = os.getenv("TENANT", TENANT_NAMESPACE.removeprefix("tenant-"))
LOCAL_QUEUE = os.getenv("LOCAL_QUEUE", TENANT)
API_TOKEN = os.getenv("TENANT_API_TOKEN", "")
COUNT_RESOURCE = os.getenv("HAMI_COUNT_RESOURCE", "nvidia.com/gpu")
MEMORY_RESOURCE = os.getenv("HAMI_MEMORY_RESOURCE", "nvidia.com/gpumem")
CORE_RESOURCE = os.getenv("HAMI_CORE_RESOURCE", "nvidia.com/gpucores")
ALLOWED_REGISTRIES = tuple(item.strip() for item in os.getenv("ALLOWED_REGISTRIES", "192.168.0.56:5000,docker.io/nvidia,nvcr.io/nvidia").split(",") if item.strip())
KFP_ENDPOINT = os.getenv("KFP_ENDPOINT", "http://ml-pipeline.kubeflow.svc.cluster.local:8888")
KFP_RUNNER_SERVICE_ACCOUNT = os.getenv("KFP_RUNNER_SERVICE_ACCOUNT", f"pipeline-runner-{TENANT}")
CATALOG_URL = os.getenv("RESOURCE_CATALOG_URL", "http://resource-catalog.science-ai-system.svc.cluster.local:8000").rstrip("/")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow.science-ai-mlops.svc.cluster.local:5000").rstrip("/")
MLFLOW_EVIDENCE_EXPERIMENT = os.getenv("MLFLOW_EVIDENCE_EXPERIMENT", "nais-kfp-mlflow-integration")
MLFLOW_EVIDENCE_MODEL = os.getenv("MLFLOW_EVIDENCE_MODEL", "nais-kfp-mean-baseline")
KFP_EVIDENCE_RUN_NAME = os.getenv("KFP_EVIDENCE_RUN_NAME", "nais-kfp-mlflow-integration")
PLATFORM_VERSION = os.getenv("PLATFORM_VERSION", "0.3.1")
PLATFORM_PROFILE = os.getenv("PLATFORM_PROFILE", "internal-production")
PORTAL_ACCESS_MODE = os.getenv("PORTAL_ACCESS_MODE", "disabled")
PLATFORM_RUNTIME_IMAGE = os.getenv("PLATFORM_RUNTIME_IMAGE", "192.168.0.56:5000/mini-science-ai-os:0.3.1")
PORTAL_COOKIE_NAME = f"science_portal_session_{TENANT}"

REQUESTS = Counter("science_job_api_requests_total", "Science Job API requests", ["route", "method", "status"])
REJECTIONS = Counter("science_job_api_rejections_total", "Science Job API policy rejections", ["reason"])
LATENCY = Histogram("science_job_api_request_duration_seconds", "Science Job API request duration", ["route"])

_docs_enabled = env_bool("API_DOCS_ENABLED", False)
app = FastAPI(
    title="NAIS Science Workspace API",
    version=PLATFORM_VERSION,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url=None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)
app.mount("/metrics", make_asgi_app())
audit = AuditLogger("science-job-api")
_MLOPS_EVIDENCE_CACHE: dict[str, Any] = {"expires_at": 0.0, "payload": None}


@app.middleware("http")
async def portal_security_headers(request: Request, call_next: Any) -> Any:
    supplied_request_id = request.headers.get("X-Request-ID", "")
    request_id = supplied_request_id if re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", supplied_request_id) else str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    if request.url.path.startswith("/portal"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'; "
            "img-src 'self' data:; font-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        if request.url.path.endswith("/") or request.url.path.endswith(".html"):
            response.headers["Cache-Control"] = "no-store"
    return response


class ResourceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    cpu: str = Field(default="1", min_length=1, max_length=16)
    memory: str = Field(default="2Gi", min_length=1, max_length=16)
    accelerator_vendor: Literal["nvidia"] | None = Field(default=None, alias="acceleratorVendor")
    gpu_count: int = Field(default=0, ge=0, le=8, alias="gpuCount")
    gpu_memory_mib: int = Field(default=0, ge=0, le=16303, alias="gpuMemoryMiB")
    gpu_core_percent: int = Field(default=0, ge=0, le=100, alias="gpuCorePercent")

    @field_validator("cpu")
    @classmethod
    def valid_cpu(cls, value: str) -> str:
        parse_cpu_milli(value)
        return value

    @field_validator("memory")
    @classmethod
    def valid_memory(cls, value: str) -> str:
        parse_memory_bytes(value)
        return value

    @model_validator(mode="after")
    def accelerator_consistency(self) -> "ResourceSpec":
        if self.gpu_count and self.accelerator_vendor != "nvidia":
            raise ValueError("gpuCount requires acceleratorVendor=nvidia")
        if (self.gpu_memory_mib or self.gpu_core_percent) and not self.gpu_count:
            raise ValueError("GPU memory/core requires gpuCount")
        return self


class ScienceJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: str = Field(min_length=1, max_length=63, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")
    image: str = Field(min_length=3, max_length=256)
    command: list[str] = Field(min_length=1, max_length=32)
    resources: ResourceSpec = Field(default_factory=ResourceSpec)
    dataset_version: str = Field(min_length=1, max_length=128, alias="datasetVersion")
    experiment: str = Field(min_length=1, max_length=63, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
    priority: Literal["low", "normal", "high"] = "normal"
    git_commit: str = Field(default="unknown", max_length=64, alias="gitCommit")

    @field_validator("command")
    @classmethod
    def string_array_only(cls, value: list[str]) -> list[str]:
        if any(not isinstance(item, str) or not item or len(item) > 256 for item in value):
            raise ValueError("command must be a non-empty string array with entries <= 256 chars")
        return value


def _clients() -> tuple[client.CoreV1Api, client.BatchV1Api, client.CustomObjectsApi]:
    return load_kubernetes_clients()


async def authorize(request: Request) -> None:
    if not env_bool("API_REQUIRE_TOKEN", True):
        return
    supplied = request.headers.get("X-Science-Token", "")
    if API_TOKEN and supplied and secrets.compare_digest(supplied, API_TOKEN):
        return
    session = request.cookies.get(PORTAL_COOKIE_NAME, "")
    if _valid_portal_session(session):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("Origin")
            expected_origin = f"{request.url.scheme}://{request.headers.get('host', '')}"
            fetch_site = request.headers.get("Sec-Fetch-Site", "")
            if (origin and origin != expected_origin) or (not origin and fetch_site != "same-origin"):
                REJECTIONS.labels("portal-csrf").inc()
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="same-origin portal request required")
        return
    REJECTIONS.labels("invalid-token").inc()
    audit.emit(tenant=TENANT, tool_name="http", arguments={"path": request.url.path}, authorization_decision="deny", error="invalid token or portal session")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="tenant token or portal session required")


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _new_portal_session() -> tuple[str, int]:
    ttl = int(os.getenv("PORTAL_SESSION_TTL_SECONDS", "28800"))
    expires_at = int(time.time()) + ttl
    payload = _base64url(json.dumps({"tenant": TENANT, "exp": expires_at}, separators=(",", ":")).encode("utf-8"))
    signature = _base64url(hmac.new(API_TOKEN.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest())
    return f"{payload}.{signature}", expires_at


def _valid_portal_session(value: str) -> bool:
    if not API_TOKEN or not value:
        return False
    try:
        payload, supplied_signature = value.split(".", 1)
        expected_signature = _base64url(hmac.new(API_TOKEN.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest())
        if not secrets.compare_digest(supplied_signature, expected_signature):
            return False
        claims = json.loads(_base64url_decode(payload))
        return claims.get("tenant") == TENANT and int(claims.get("exp", 0)) > int(time.time())
    except (ValueError, TypeError, json.JSONDecodeError):
        return False


def _check_image(image: str) -> None:
    registry = image_registry(image)
    if not any(image == prefix or image.startswith(prefix + "/") for prefix in ALLOWED_REGISTRIES):
        REJECTIONS.labels("image-allowlist").inc()
        raise HTTPException(status_code=400, detail=f"image registry '{registry}' is not allowed")
    if "@sha256:" not in image and os.getenv("REQUIRE_IMAGE_DIGEST", "false").lower() == "true":
        REJECTIONS.labels("image-digest").inc()
        raise HTTPException(status_code=400, detail="image digest is required by this deployment")


def _check_resources(resources: ResourceSpec) -> None:
    max_cpu = int(os.getenv("TENANT_MAX_CPU_MILLI", "8000"))
    max_memory = int(os.getenv("TENANT_MAX_MEMORY_BYTES", str(16 * 1024**3)))
    max_gpu = int(os.getenv("TENANT_MAX_GPU_COUNT", "1"))
    if parse_cpu_milli(resources.cpu) > max_cpu:
        REJECTIONS.labels("cpu-limit").inc()
        raise HTTPException(status_code=400, detail="tenant CPU maximum exceeded")
    if parse_memory_bytes(resources.memory) > max_memory:
        REJECTIONS.labels("memory-limit").inc()
        raise HTTPException(status_code=400, detail="tenant memory maximum exceeded")
    if resources.gpu_count > max_gpu:
        REJECTIONS.labels("gpu-limit").inc()
        raise HTTPException(status_code=400, detail="tenant GPU maximum exceeded")


def _job_name(job_id: str) -> str:
    return f"science-{job_id}"


def _experiment_name(request: ScienceJobRequest) -> str:
    return f"{TENANT}/{request.project}/{request.experiment}"


def _resource_requirements(resources: ResourceSpec) -> dict[str, str]:
    values = {"cpu": resources.cpu, "memory": resources.memory}
    if resources.gpu_count:
        values[COUNT_RESOURCE] = str(resources.gpu_count)
        if resources.gpu_memory_mib:
            values[MEMORY_RESOURCE] = str(resources.gpu_memory_mib)
        if resources.gpu_core_percent:
            values[CORE_RESOURCE] = str(resources.gpu_core_percent)
    return values


def build_job(job_id: str, request: ScienceJobRequest, *, is_demo: bool = False) -> client.V1Job:
    labels = {
        "science-ai.io/managed-by": "mini-science-ai-os",
        "science-ai.io/demo": "true" if is_demo else "false",
        "science-ai.io/tenant": TENANT,
        "science-ai.io/project": request.project,
        "science-ai.io/experiment": request.experiment,
        "science-ai.io/job-id": job_id,
        "kueue.x-k8s.io/queue-name": LOCAL_QUEUE,
    }
    priority_class = f"science-{request.priority}"
    labels["kueue.x-k8s.io/priority-class"] = priority_class
    resources = _resource_requirements(request.resources)
    pod_metadata = client.V1ObjectMeta(labels=labels, annotations={"science-ai.io/dataset-version": request.dataset_version})
    env = [
        client.V1EnvVar(name="SCIENCE_JOB_ID", value=job_id),
        client.V1EnvVar(name="SCIENCE_TENANT", value=TENANT),
        client.V1EnvVar(name="SCIENCE_PROJECT", value=request.project),
        client.V1EnvVar(name="SCIENCE_DATASET_VERSION", value=request.dataset_version),
        client.V1EnvVar(name="SCIENCE_EXPERIMENT", value=_experiment_name(request)),
        client.V1EnvVar(name="SCIENCE_GIT_COMMIT", value=request.git_commit),
        client.V1EnvVar(name="SCIENCE_CONTAINER_IMAGE", value=request.image),
    ]
    container = client.V1Container(
        name="science-job",
        image=request.image,
        image_pull_policy="IfNotPresent",
        command=request.command,
        env=env,
        resources=client.V1ResourceRequirements(requests=resources, limits=resources),
        security_context=client.V1SecurityContext(
            allow_privilege_escalation=False,
            read_only_root_filesystem=True,
            capabilities=client.V1Capabilities(drop=["ALL"]),
            seccomp_profile=client.V1SeccompProfile(type="RuntimeDefault"),
        ),
    )
    pod_spec = client.V1PodSpec(
        restart_policy="Never",
        service_account_name="science-job-runner",
        automount_service_account_token=False,
        priority_class_name=priority_class,
        node_selector={"environment": "cloud", "kubernetes.io/arch": "amd64"},
        scheduler_name="hami-scheduler" if request.resources.gpu_count else "default-scheduler",
        security_context=client.V1PodSecurityContext(
            run_as_non_root=True,
            run_as_user=10001,
            run_as_group=10001,
            fs_group=10001,
            seccomp_profile=client.V1SeccompProfile(type="RuntimeDefault"),
        ),
        containers=[container],
        volumes=[client.V1Volume(name="tmp", empty_dir=client.V1EmptyDirVolumeSource(medium="Memory", size_limit="256Mi"))],
    )
    container.volume_mounts = [client.V1VolumeMount(name="tmp", mount_path="/tmp")]
    pod = client.V1PodTemplateSpec(metadata=pod_metadata, spec=pod_spec)
    return client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=_job_name(job_id), labels=labels),
        spec=client.V1JobSpec(
            suspend=True,
            backoff_limit=1,
            ttl_seconds_after_finished=int(os.getenv("JOB_TTL_SECONDS", "86400")),
            active_deadline_seconds=int(os.getenv("JOB_MAX_SECONDS", "3600")),
            template=pod,
        ),
    )


def _job_status(job: Any, workload: dict[str, Any] | None = None) -> dict[str, Any]:
    status_value = job.status.to_dict() if job.status else {}
    result: dict[str, Any] = {
        "jobId": (job.metadata.labels or {}).get("science-ai.io/job-id"),
        "name": job.metadata.name,
        "tenant": TENANT,
        "project": (job.metadata.labels or {}).get("science-ai.io/project"),
        "experiment": (job.metadata.labels or {}).get("science-ai.io/experiment"),
        "status": "running" if status_value.get("active") else "pending",
        "succeeded": status_value.get("succeeded", 0),
        "failed": status_value.get("failed", 0),
        "conditions": status_value.get("conditions", []),
    }
    if status_value.get("succeeded"):
        result["status"] = "succeeded"
    elif status_value.get("failed"):
        result["status"] = "failed"
    if workload:
        result["queue"] = {
            "name": workload.get("spec", {}).get("queueName"),
            "admission": workload.get("status", {}).get("admission"),
            "conditions": workload.get("status", {}).get("conditions", []),
            "requeueState": workload.get("status", {}).get("requeueState"),
        }
    return result


def _workload_for(custom: client.CustomObjectsApi, job_name: str) -> dict[str, Any] | None:
    try:
        payload = custom.list_namespaced_custom_object(group="kueue.x-k8s.io", version="v1beta1", namespace=TENANT_NAMESPACE, plural="workloads")
    except Exception:
        return None
    for workload in payload.get("items", []):
        owner_names = {ref.get("name") for ref in workload.get("metadata", {}).get("ownerReferences", [])}
        labels = workload.get("metadata", {}).get("labels", {})
        if job_name in owner_names or labels.get("kueue.x-k8s.io/job-name") == job_name:
            return workload
    return None


def _find_job(batch: client.BatchV1Api, job_id: str) -> client.V1Job:
    try:
        return batch.read_namespaced_job(_job_name(job_id), TENANT_NAMESPACE)
    except client.ApiException as exc:
        if exc.status == 404:
            raise HTTPException(status_code=404, detail="job not found") from exc
        raise HTTPException(status_code=502, detail="Kubernetes API read failed") from exc


def _optional_job(batch: client.BatchV1Api, job_id: str) -> client.V1Job | None:
    try:
        return batch.read_namespaced_job(_job_name(job_id), TENANT_NAMESPACE)
    except client.ApiException as exc:
        if exc.status == 404:
            return None
        raise


def _mapping_name(job_id: str) -> str:
    return f"science-run-{job_id}"


def _read_mapping(core: client.CoreV1Api, job_id: str) -> client.V1ConfigMap:
    try:
        return core.read_namespaced_config_map(_mapping_name(job_id), TENANT_NAMESPACE)
    except client.ApiException as exc:
        if exc.status == 404:
            raise HTTPException(status_code=404, detail="job not found") from exc
        raise HTTPException(status_code=502, detail="Kubernetes API mapping read failed") from exc


def _kubeflow_client() -> KubeflowClient:
    return KubeflowClient(host=KFP_ENDPOINT)


def _submit_kubeflow_run(job_id: str, payload: ScienceJobRequest) -> str:
    result = _kubeflow_client().create_run_from_pipeline_func(
        science_job_pipeline,
        arguments={
            "job_id": job_id,
            "tenant": TENANT,
            "namespace": TENANT_NAMESPACE,
            "project": payload.project,
            "experiment": payload.experiment,
            "image": payload.image,
            "command_json": json.dumps(payload.command),
            "dataset_version": payload.dataset_version,
            "git_commit": payload.git_commit,
            "priority": payload.priority,
            "local_queue": LOCAL_QUEUE,
            "cpu": payload.resources.cpu,
            "memory": payload.resources.memory,
            "gpu_count": payload.resources.gpu_count,
            "gpu_memory_mib": payload.resources.gpu_memory_mib,
            "gpu_core_percent": payload.resources.gpu_core_percent,
            "count_resource": COUNT_RESOURCE,
            "memory_resource": MEMORY_RESOURCE,
            "core_resource": CORE_RESOURCE,
            "max_seconds": int(os.getenv("JOB_MAX_SECONDS", "3600")),
        },
        run_name=_job_name(job_id),
        experiment_name=_experiment_name(payload),
        pipeline_root="s3://kubeflow-pipelines/v2/artifacts",
        enable_caching=False,
        service_account=KFP_RUNNER_SERVICE_ACCOUNT,
    )
    return result.run_id


def _kubeflow_run_status(run_id: str) -> dict[str, Any]:
    try:
        run = _kubeflow_client().get_run(run_id)
    except Exception as exc:
        return {"runId": run_id, "state": "UNKNOWN", "error": type(exc).__name__}
    return {
        "runId": run_id,
        "state": str(getattr(run, "state", "UNKNOWN")),
        "displayName": getattr(run, "display_name", None),
        "createdAt": str(getattr(run, "created_at", "")),
        "finishedAt": str(getattr(run, "finished_at", "")),
    }


def _mapping_status(mapping: client.V1ConfigMap, batch: client.BatchV1Api, custom: client.CustomObjectsApi) -> dict[str, Any]:
    data = mapping.data or {}
    job_id = (mapping.metadata.labels or {}).get("science-ai.io/job-id", "")
    job = _optional_job(batch, job_id)
    if job:
        result = _job_status(job, _workload_for(custom, job.metadata.name))
    else:
        result = {
            "jobId": job_id,
            "name": _job_name(job_id),
            "tenant": TENANT,
            "project": (mapping.metadata.labels or {}).get("science-ai.io/project"),
            "experiment": (mapping.metadata.labels or {}).get("science-ai.io/experiment"),
            "status": data.get("status", "submitted"),
        }
    result["kubeflow"] = _kubeflow_run_status(data["run_id"]) if data.get("run_id") else {"state": "SUBMITTING"}
    result["createdAt"] = str(mapping.metadata.creation_timestamp or "")
    if data.get("request"):
        try:
            result["request"] = json.loads(data["request"])
        except json.JSONDecodeError:
            result["request"] = None
    return result


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "tenant": TENANT, "portal": "/portal/", "version": app.version}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    if not API_TOKEN:
        raise HTTPException(status_code=503, detail="tenant session signing key is unavailable")
    if TENANT != "etri" or TENANT_NAMESPACE != "tenant-etri":
        raise HTTPException(status_code=503, detail="internal product scope is not configured")
    if PLATFORM_PROFILE == "internal-production" and PORTAL_ACCESS_MODE != "trusted-network":
        raise HTTPException(status_code=503, detail="trusted-network portal mode is not configured")
    return {
        "status": "ready",
        "tenant": TENANT,
        "namespace": TENANT_NAMESPACE,
        "version": app.version,
        "profile": PLATFORM_PROFILE,
        "accessMode": PORTAL_ACCESS_MODE,
    }


@app.get("/", include_in_schema=False)
async def product_root() -> RedirectResponse:
    return RedirectResponse(url="/portal/", status_code=307)


@app.post("/v1/portal/session")
async def create_portal_session(response: Response) -> dict[str, Any]:
    legacy_demo_mode = env_bool("PORTAL_ANONYMOUS_ACCESS", False)
    if PORTAL_ACCESS_MODE != "trusted-network" and not legacy_demo_mode:
        raise HTTPException(status_code=404, detail="portal trusted-network access is disabled")
    if not API_TOKEN:
        raise HTTPException(status_code=503, detail="portal session signing is unavailable")
    session, expires_at = _new_portal_session()
    ttl = int(os.getenv("PORTAL_SESSION_TTL_SECONDS", "28800"))
    response.set_cookie(
        key=PORTAL_COOKIE_NAME,
        value=session,
        max_age=ttl,
        httponly=True,
        secure=env_bool("PORTAL_COOKIE_SECURE", False),
        samesite="strict",
        path="/",
    )
    audit.emit(
        tenant=TENANT,
        tool_name="create_portal_session",
        arguments={"mode": PORTAL_ACCESS_MODE if not legacy_demo_mode else "legacy-internal-demo"},
        authorization_decision="allow",
        result={"expires_at": expires_at},
    )
    return {"status": "connected", "tenant": TENANT, "expiresAt": expires_at}


@app.delete("/v1/portal/session")
async def delete_portal_session(response: Response) -> dict[str, str]:
    response.delete_cookie(key=PORTAL_COOKIE_NAME, path="/", samesite="strict")
    return {"status": "disconnected", "tenant": TENANT}


@app.get("/v1/config", dependencies=[Depends(authorize)])
async def portal_config() -> dict[str, Any]:
    return {
        "platformName": "NAIS Science Workspace",
        "edition": "Internal",
        "version": PLATFORM_VERSION,
        "deploymentProfile": PLATFORM_PROFILE,
        "accessMode": PORTAL_ACCESS_MODE,
        "tenant": TENANT,
        "namespace": TENANT_NAMESPACE,
        "localQueue": LOCAL_QUEUE,
        "allowedRegistries": list(ALLOWED_REGISTRIES),
        "defaultImage": PLATFORM_RUNTIME_IMAGE,
        "limits": {
            "cpuMilli": int(os.getenv("TENANT_MAX_CPU_MILLI", "8000")),
            "memoryBytes": int(os.getenv("TENANT_MAX_MEMORY_BYTES", str(16 * 1024**3))),
            "gpuCount": int(os.getenv("TENANT_MAX_GPU_COUNT", "1")),
            "jobMaxSeconds": int(os.getenv("JOB_MAX_SECONDS", "3600")),
            "jobTtlSeconds": int(os.getenv("JOB_TTL_SECONDS", "86400")),
        },
        "acceleratorResources": {
            "count": COUNT_RESOURCE,
            "memory": MEMORY_RESOURCE,
            "core": CORE_RESOURCE,
        },
    }


@app.get("/v1/resources/summary", dependencies=[Depends(authorize)])
async def resource_summary() -> dict[str, Any]:
    return await _catalog_payload("/v1/resources/summary", "resources")


async def _catalog_payload(path: str, metric: str) -> dict[str, Any]:
    try:
        async with httpx2.AsyncClient(timeout=5.0) as http:
            response = await http.get(f"{CATALOG_URL}{path}")
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        REQUESTS.labels(metric, "GET", "502").inc()
        raise HTTPException(status_code=502, detail=f"Resource Catalog unavailable: {type(exc).__name__}") from exc
    REQUESTS.labels(metric, "GET", "200").inc()
    return payload


@app.get("/v1/topology", dependencies=[Depends(authorize)])
async def topology() -> dict[str, Any]:
    return await _catalog_payload("/v1/topology", "topology")


@app.get("/v1/operations", dependencies=[Depends(authorize)])
async def operations() -> dict[str, Any]:
    payload = await _catalog_payload("/v1/operations", "operations")
    payload["mlops"] = await _mlops_evidence()
    return payload


def _latest_kfp_evidence_run() -> dict[str, Any]:
    response = _kubeflow_client().list_runs(
        page_size=1,
        sort_by="created_at desc",
        filter=json.dumps(
            {
                "predicates": [
                    {
                        "operation": "EQUALS",
                        "key": "display_name",
                        "stringValue": KFP_EVIDENCE_RUN_NAME,
                    }
                ]
            }
        ),
    )
    runs = response.runs or []
    if not runs:
        return {"status": "not-found", "runName": KFP_EVIDENCE_RUN_NAME}
    run = runs[0]
    duration = None
    if run.created_at and run.finished_at:
        duration = max(0, int((run.finished_at - run.created_at).total_seconds()))
    return {
        "status": "ready",
        "runId": run.run_id,
        "runName": run.display_name,
        "state": str(run.state or "UNKNOWN"),
        "createdAt": run.created_at.isoformat() if run.created_at else None,
        "finishedAt": run.finished_at.isoformat() if run.finished_at else None,
        "durationSeconds": duration,
    }


def _mlflow_metric(run: dict[str, Any], key: str) -> float | None:
    for metric in run.get("data", {}).get("metrics", []):
        if metric.get("key") == key:
            try:
                return float(metric.get("value"))
            except (TypeError, ValueError):
                return None
    return None


async def _mlflow_evidence() -> dict[str, Any]:
    async with httpx2.AsyncClient(timeout=5.0) as http:
        experiment_response = await http.get(
            f"{MLFLOW_TRACKING_URI}/api/2.0/mlflow/experiments/get-by-name",
            params={"experiment_name": MLFLOW_EVIDENCE_EXPERIMENT},
        )
        experiment_response.raise_for_status()
        experiment = experiment_response.json()["experiment"]

        runs_response = await http.post(
            f"{MLFLOW_TRACKING_URI}/api/2.0/mlflow/runs/search",
            json={
                "experiment_ids": [experiment["experiment_id"]],
                "max_results": 1,
                "order_by": ["attributes.start_time DESC"],
            },
        )
        runs_response.raise_for_status()
        runs = runs_response.json().get("runs", [])
        if not runs:
            return {
                "status": "not-found",
                "experimentId": experiment["experiment_id"],
                "experimentName": experiment["name"],
            }
        run = runs[0]

        model_response = await http.get(
            f"{MLFLOW_TRACKING_URI}/api/2.0/mlflow/registered-models/alias",
            params={"name": MLFLOW_EVIDENCE_MODEL, "alias": "candidate"},
        )
        model_response.raise_for_status()
        model = model_response.json()["model_version"]

    return {
        "status": "ready",
        "experimentId": experiment["experiment_id"],
        "experimentName": experiment["name"],
        "run": {
            "runId": run.get("info", {}).get("run_id"),
            "runName": run.get("info", {}).get("run_name"),
            "status": run.get("info", {}).get("status"),
            "startedAt": run.get("info", {}).get("start_time"),
            "mae": _mlflow_metric(run, "mae"),
            "samples": _mlflow_metric(run, "samples"),
        },
        "model": {
            "name": model.get("name"),
            "version": model.get("version"),
            "status": model.get("status"),
            "alias": "candidate" if "candidate" in model.get("aliases", []) else None,
            "runId": model.get("run_id"),
        },
    }


async def _mlops_evidence() -> dict[str, Any]:
    now = time.monotonic()
    cached = _MLOPS_EVIDENCE_CACHE.get("payload")
    if cached is not None and now < float(_MLOPS_EVIDENCE_CACHE.get("expires_at", 0)):
        return cached

    try:
        kfp = await run_in_threadpool(_latest_kfp_evidence_run)
    except Exception as exc:
        kfp = {"status": "unavailable", "reason": type(exc).__name__}
    try:
        mlflow = await _mlflow_evidence()
    except Exception as exc:
        mlflow = {"status": "unavailable", "reason": type(exc).__name__}

    payload = {
        "generatedAt": int(time.time() * 1000),
        "kfp": kfp,
        "mlflow": mlflow,
    }
    _MLOPS_EVIDENCE_CACHE.update({"expires_at": now + 15.0, "payload": payload})
    return payload


def _placement_for_job(topology_payload: dict[str, Any], job_id: str) -> dict[str, Any] | None:
    for site in topology_payload.get("sites", []):
        for node in site.get("nodes", []):
            for workload in node.get("gpuWorkloads", []):
                if workload.get("jobId") != job_id:
                    continue
                return {
                    "site": site.get("site"),
                    "node": node.get("node"),
                    "nodeHealth": node.get("health"),
                    "gpuModel": (node.get("accelerator") or {}).get("model"),
                    "pod": workload.get("pod"),
                    "phase": workload.get("phase"),
                    "active": workload.get("active"),
                    "allocations": workload.get("allocations", []),
                }
    return None


@app.post("/v1/jobs", dependencies=[Depends(authorize)])
async def submit_job(request: Request, payload: ScienceJobRequest) -> dict[str, Any]:
    _check_image(payload.image)
    _check_resources(payload.resources)
    job_id = uuid.uuid4().hex[:12]
    core, _, _ = _clients()
    labels = {
        "science-ai.io/managed-by": "mini-science-ai-os",
        "science-ai.io/tenant": TENANT,
        "science-ai.io/project": payload.project,
        "science-ai.io/experiment": payload.experiment,
        "science-ai.io/job-id": job_id,
        "science-ai.io/demo": "true" if request.headers.get("X-Science-Demo", "false").lower() == "true" else "false",
    }
    mapping = client.V1ConfigMap(
        metadata=client.V1ObjectMeta(name=_mapping_name(job_id), namespace=TENANT_NAMESPACE, labels=labels),
        data={
            "status": "submitting",
            "request": payload.model_dump_json(by_alias=True),
            "experiment_name": _experiment_name(payload),
        },
    )
    try:
        core.create_namespaced_config_map(TENANT_NAMESPACE, mapping)
        run_id = await run_in_threadpool(_submit_kubeflow_run, job_id, payload)
        core.patch_namespaced_config_map(_mapping_name(job_id), TENANT_NAMESPACE, {"data": {"run_id": run_id, "status": "submitted"}})
    except client.ApiException as exc:
        REQUESTS.labels("jobs", "POST", str(exc.status or 500)).inc()
        raise HTTPException(status_code=502, detail="Kubernetes mapping create failed") from exc
    except Exception as exc:
        try:
            core.delete_namespaced_config_map(_mapping_name(job_id), TENANT_NAMESPACE)
        except client.ApiException:
            pass
        REQUESTS.labels("jobs", "POST", "502").inc()
        raise HTTPException(status_code=502, detail=f"Kubeflow run submission failed: {type(exc).__name__}") from exc
    REQUESTS.labels("jobs", "POST", "201").inc()
    audit.emit(tenant=TENANT, tool_name="submit_science_job", arguments=payload.model_dump(by_alias=True), authorization_decision="allow", linked_job_id=job_id, result={"name": _job_name(job_id), "kubeflow_run_id": run_id})
    return {"jobId": job_id, "name": _job_name(job_id), "namespace": TENANT_NAMESPACE, "queue": LOCAL_QUEUE, "kubeflowRunId": run_id, "status": "submitted"}


@app.get("/v1/jobs", dependencies=[Depends(authorize)])
async def list_jobs() -> dict[str, Any]:
    core, batch, custom = _clients()
    mappings = core.list_namespaced_config_map(TENANT_NAMESPACE, label_selector="science-ai.io/managed-by=mini-science-ai-os,science-ai.io/job-id").items
    jobs = [_mapping_status(mapping, batch, custom) for mapping in mappings]
    jobs.sort(key=lambda item: item.get("createdAt", ""), reverse=True)
    return {"jobs": jobs}


@app.get("/v1/jobs/{job_id}", dependencies=[Depends(authorize)])
async def get_job(job_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{12}", job_id):
        raise HTTPException(status_code=400, detail="invalid job id")
    core, batch, custom = _clients()
    result = _mapping_status(_read_mapping(core, job_id), batch, custom)
    try:
        result["placement"] = _placement_for_job(await _catalog_payload("/v1/topology", "topology"), job_id)
    except HTTPException:
        result["placement"] = None
    return result


@app.delete("/v1/jobs/{job_id}", dependencies=[Depends(authorize)])
async def delete_job(job_id: str) -> dict[str, str]:
    core, batch, _ = _clients()
    mapping = _read_mapping(core, job_id)
    labels = mapping.metadata.labels or {}
    if labels.get("science-ai.io/tenant") != TENANT:
        raise HTTPException(status_code=403, detail="job belongs to another tenant")
    run_id = (mapping.data or {}).get("run_id")
    try:
        if run_id:
            await run_in_threadpool(_kubeflow_client().terminate_run, run_id)
        if _optional_job(batch, job_id):
            batch.delete_namespaced_job(_job_name(job_id), TENANT_NAMESPACE, propagation_policy="Foreground")
        core.delete_namespaced_config_map(_mapping_name(job_id), TENANT_NAMESPACE)
    except client.ApiException as exc:
        raise HTTPException(status_code=502, detail="Kubernetes API delete failed") from exc
    audit.emit(tenant=TENANT, tool_name="cancel_own_job", arguments={"job_id": job_id}, authorization_decision="allow", linked_job_id=job_id, result={"status": "deleted"})
    return {"jobId": job_id, "status": "deleted"}


@app.get("/v1/jobs/{job_id}/metrics", dependencies=[Depends(authorize)])
async def job_metrics(job_id: str) -> dict[str, Any]:
    core, _, _ = _clients()
    data = _read_mapping(core, job_id).data or {}
    return {
        "jobId": job_id,
        "kubeflowRunId": data.get("run_id"),
        "status": data.get("status", "submitted"),
        "metrics": json.loads(data.get("metrics", "{}")),
        "params": json.loads(data.get("params", "{}")),
    }


@app.get("/v1/jobs/{job_id}/artifacts", dependencies=[Depends(authorize)])
async def job_artifacts(job_id: str) -> dict[str, Any]:
    core, _, _ = _clients()
    data = _read_mapping(core, job_id).data or {}
    artifact = json.loads(data["artifact"]) if data.get("artifact") else None
    return {
        "jobId": job_id,
        "kubeflowRunId": data.get("run_id"),
        "pipelineRoot": "s3://kubeflow-pipelines/v2/artifacts",
        "artifacts": [artifact] if artifact else [],
    }


@app.get("/v1/experiments/{experiment}/runs", dependencies=[Depends(authorize)])
async def experiment_runs(experiment: str) -> dict[str, Any]:
    core, batch, custom = _clients()
    mappings = core.list_namespaced_config_map(TENANT_NAMESPACE, label_selector=f"science-ai.io/experiment={experiment},science-ai.io/managed-by=mini-science-ai-os").items
    return {"tenant": TENANT, "experiment": experiment, "jobs": [_mapping_status(mapping, batch, custom) for mapping in mappings]}


PORTAL_DIRECTORY = Path(__file__).with_name("portal")
app.mount("/portal", StaticFiles(directory=PORTAL_DIRECTORY, html=True), name="portal")
