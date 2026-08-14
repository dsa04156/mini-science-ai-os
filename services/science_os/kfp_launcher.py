from __future__ import annotations

import ast
import json
import time
from pathlib import Path
from typing import Any

from kubernetes import client, config


def _resource_requirements(
    *,
    cpu: str,
    memory: str,
    gpu_count: int,
    gpu_memory_mib: int,
    gpu_core_percent: int,
    count_resource: str,
    memory_resource: str,
    core_resource: str,
) -> dict[str, str]:
    values = {"cpu": cpu, "memory": memory}
    if gpu_count:
        values[count_resource] = str(gpu_count)
        if gpu_memory_mib:
            values[memory_resource] = str(gpu_memory_mib)
        if gpu_core_percent:
            values[core_resource] = str(gpu_core_percent)
    return values


def build_child_job(
    *,
    job_id: str,
    tenant: str,
    namespace: str,
    project: str,
    experiment: str,
    image: str,
    command: list[str],
    dataset_version: str,
    git_commit: str,
    priority: str,
    local_queue: str,
    cpu: str,
    memory: str,
    gpu_count: int,
    gpu_memory_mib: int,
    gpu_core_percent: int,
    count_resource: str,
    memory_resource: str,
    core_resource: str,
    max_seconds: int,
) -> client.V1Job:
    labels = {
        "science-ai.io/managed-by": "mini-science-ai-os",
        "science-ai.io/demo": "true",
        "science-ai.io/tenant": tenant,
        "science-ai.io/project": project,
        "science-ai.io/experiment": experiment,
        "science-ai.io/job-id": job_id,
        "science-ai.io/orchestrator": "kubeflow",
        "kueue.x-k8s.io/queue-name": local_queue,
        "kueue.x-k8s.io/priority-class": f"science-{priority}",
    }
    values = _resource_requirements(
        cpu=cpu,
        memory=memory,
        gpu_count=gpu_count,
        gpu_memory_mib=gpu_memory_mib,
        gpu_core_percent=gpu_core_percent,
        count_resource=count_resource,
        memory_resource=memory_resource,
        core_resource=core_resource,
    )
    container = client.V1Container(
        name="science-job",
        image=image,
        image_pull_policy="IfNotPresent",
        command=command,
        env=[
            client.V1EnvVar(name="SCIENCE_JOB_ID", value=job_id),
            client.V1EnvVar(name="SCIENCE_TENANT", value=tenant),
            client.V1EnvVar(name="SCIENCE_PROJECT", value=project),
            client.V1EnvVar(name="SCIENCE_EXPERIMENT", value=f"{tenant}/{project}/{experiment}"),
            client.V1EnvVar(name="SCIENCE_DATASET_VERSION", value=dataset_version),
            client.V1EnvVar(name="SCIENCE_GIT_COMMIT", value=git_commit),
            client.V1EnvVar(name="SCIENCE_CONTAINER_IMAGE", value=image),
        ],
        resources=client.V1ResourceRequirements(requests=values, limits=values),
        security_context=client.V1SecurityContext(
            allow_privilege_escalation=False,
            read_only_root_filesystem=True,
            capabilities=client.V1Capabilities(drop=["ALL"]),
            seccomp_profile=client.V1SeccompProfile(type="RuntimeDefault"),
        ),
        volume_mounts=[client.V1VolumeMount(name="tmp", mount_path="/tmp")],
    )
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(
            labels=labels,
            annotations={"science-ai.io/dataset-version": dataset_version},
        ),
        spec=client.V1PodSpec(
            restart_policy="Never",
            service_account_name="science-job-runner",
            automount_service_account_token=False,
            priority_class_name=f"science-{priority}",
            node_selector={"environment": "cloud", "kubernetes.io/arch": "amd64"},
            scheduler_name="hami-scheduler" if gpu_count else "default-scheduler",
            security_context=client.V1PodSecurityContext(
                run_as_non_root=True,
                run_as_user=10001,
                run_as_group=10001,
                fs_group=10001,
                seccomp_profile=client.V1SeccompProfile(type="RuntimeDefault"),
            ),
            containers=[container],
            volumes=[
                client.V1Volume(
                    name="tmp",
                    empty_dir=client.V1EmptyDirVolumeSource(medium="Memory", size_limit="256Mi"),
                )
            ],
        ),
    )
    return client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=f"science-{job_id}", namespace=namespace, labels=labels),
        spec=client.V1JobSpec(
            suspend=True,
            backoff_limit=1,
            ttl_seconds_after_finished=86400,
            active_deadline_seconds=max_seconds,
            template=template,
        ),
    )


def _last_result(log_text: str) -> dict[str, Any]:
    for line in reversed(log_text.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            try:
                value = ast.literal_eval(line)
            except (SyntaxError, ValueError):
                continue
        if isinstance(value, dict) and value.get("science_job_id"):
            return value
    raise RuntimeError("science job did not emit a structured result")


def launch_and_collect(
    *,
    metrics_output: Any,
    artifact_output: Any,
    job_id: str,
    tenant: str,
    namespace: str,
    project: str,
    experiment: str,
    image: str,
    command_json: str,
    dataset_version: str,
    git_commit: str,
    priority: str,
    local_queue: str,
    cpu: str,
    memory: str,
    gpu_count: int,
    gpu_memory_mib: int,
    gpu_core_percent: int,
    count_resource: str,
    memory_resource: str,
    core_resource: str,
    max_seconds: int,
) -> None:
    config.load_incluster_config()
    core = client.CoreV1Api()
    batch = client.BatchV1Api()
    command = json.loads(command_json)
    if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
        raise ValueError("command_json must encode a string array")
    job = build_child_job(
        job_id=job_id,
        tenant=tenant,
        namespace=namespace,
        project=project,
        experiment=experiment,
        image=image,
        command=command,
        dataset_version=dataset_version,
        git_commit=git_commit,
        priority=priority,
        local_queue=local_queue,
        cpu=cpu,
        memory=memory,
        gpu_count=gpu_count,
        gpu_memory_mib=gpu_memory_mib,
        gpu_core_percent=gpu_core_percent,
        count_resource=count_resource,
        memory_resource=memory_resource,
        core_resource=core_resource,
        max_seconds=max_seconds,
    )
    batch.create_namespaced_job(namespace, job)
    deadline = time.monotonic() + max_seconds + 300
    status = "pending"
    while time.monotonic() < deadline:
        current = batch.read_namespaced_job(f"science-{job_id}", namespace)
        if current.status and current.status.succeeded:
            status = "succeeded"
            break
        if current.status and current.status.failed:
            status = "failed"
            break
        time.sleep(2)
    else:
        status = "timeout"

    pods = core.list_namespaced_pod(namespace, label_selector=f"job-name=science-{job_id}").items
    pod = pods[0] if pods else None
    log_text = core.read_namespaced_pod_log(pod.metadata.name, namespace) if pod else ""
    result: dict[str, Any]
    try:
        result = _last_result(log_text)
    except RuntimeError:
        result = {
            "science_job_id": job_id,
            "tenant": tenant,
            "project": project,
            "experiment": f"{tenant}/{project}/{experiment}",
            "dataset_version": dataset_version,
            "git_commit": git_commit,
            "container_image": image,
            "node": pod.spec.node_name if pod else None,
            "accelerator": "gpu" if gpu_count else "cpu",
            "params": {},
            "metrics": {},
            "status": status,
            "job_log_tail": log_text[-2000:],
        }
    result["status"] = status
    result["node"] = pod.spec.node_name if pod else result.get("node")
    result["kubeflow_pipeline"] = True

    for name, value in result.get("metrics", {}).items():
        if isinstance(value, (int, float)):
            metrics_output.log_metric(name, float(value))
    artifact_output.metadata.update(
        {
            "tenant": tenant,
            "project": project,
            "job_id": job_id,
            "dataset_version": dataset_version,
            "container_image": image,
        }
    )
    Path(artifact_output.path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    core.patch_namespaced_config_map(
        f"science-run-{job_id}",
        namespace,
        {"data": {
            "status": status,
            "metrics": json.dumps(result.get("metrics", {})),
            "params": json.dumps(result.get("params", {})),
            "artifact": json.dumps(result),
            "node": str(result.get("node") or "unknown"),
        }},
    )
    if status != "succeeded":
        raise RuntimeError(f"child science job finished with status={status}")
