from __future__ import annotations

import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kubernetes import client, config


SENSITIVE_WORDS = (
    "password",
    "secret",
    "token",
    "authorization",
    "credential",
    "private_key",
    "hmac",
    "dataset_path",
    "datasetpath",
)


def load_kubernetes_clients() -> tuple[client.CoreV1Api, client.BatchV1Api, client.CustomObjectsApi]:
    """Load in-cluster clients, with local kubeconfig as a test-only fallback."""

    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    api_client = client.ApiClient()
    return client.CoreV1Api(api_client), client.BatchV1Api(api_client), client.CustomObjectsApi(api_client)


def sanitize(value: Any) -> Any:
    """Recursively mask values that must not cross an audit boundary."""

    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if any(word in str(key).lower() for word in SENSITIVE_WORDS) else sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, str) and ("Bearer " in value or "eyJ" in value):
        return "[REDACTED]"
    return value


class AuditLogger:
    def __init__(self, component: str) -> None:
        self.component = component
        self.path = os.getenv("AUDIT_LOG_PATH", "")

    def emit(
        self,
        *,
        tenant: str,
        tool_name: str,
        arguments: Any,
        authorization_decision: str,
        linked_job_id: str | None = None,
        result: Any = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        event = {
            "request_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": self.component,
            "tenant": tenant,
            "tool_name": tool_name,
            "sanitized_arguments": sanitize(arguments),
            "authorization_decision": authorization_decision,
            "linked_job_id": linked_job_id,
            "result": sanitize(result),
            "error": error,
        }
        line = json.dumps(event, separators=(",", ":"), sort_keys=True, default=str)
        print(line, file=sys.stdout, flush=True)
        if self.path:
            path = Path(self.path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as stream:
                stream.write(line + "\n")
        return event


def parse_cpu_milli(value: str) -> int:
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(m)?", value)
    if not match:
        raise ValueError("cpu must be a Kubernetes quantity such as 500m or 2")
    number = float(match.group(1))
    return int(number if match.group(2) else number * 1000)


def parse_memory_bytes(value: str) -> int:
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(Ki|Mi|Gi|Ti|K|M|G|T)?", value)
    if not match:
        raise ValueError("memory must be a Kubernetes quantity such as 4Gi")
    number = float(match.group(1))
    factors = {"Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4, "K": 1000, "M": 1000**2, "G": 1000**3, "T": 1000**4}
    return int(number * factors.get(match.group(2) or "", 1))


def image_registry(image: str) -> str:
    first = image.split("/", 1)[0]
    if "." in first or ":" in first or first == "localhost":
        return first
    return "docker.io"


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}
