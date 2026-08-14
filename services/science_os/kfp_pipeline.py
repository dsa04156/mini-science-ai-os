import os

from kfp import dsl, kubernetes


RUNTIME_IMAGE = os.getenv("PLATFORM_RUNTIME_IMAGE", "192.168.0.56:5000/mini-science-ai-os:0.3.1")


@dsl.component(base_image=RUNTIME_IMAGE)
def launch_science_job(
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
    metrics: dsl.Output[dsl.Metrics],
    result: dsl.Output[dsl.Artifact],
) -> None:
    from science_os.kfp_launcher import launch_and_collect

    launch_and_collect(
        metrics_output=metrics,
        artifact_output=result,
        job_id=job_id,
        tenant=tenant,
        namespace=namespace,
        project=project,
        experiment=experiment,
        image=image,
        command_json=command_json,
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


@dsl.pipeline(name="mini-science-job")
def science_job_pipeline(
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
    task = launch_science_job(
        job_id=job_id,
        tenant=tenant,
        namespace=namespace,
        project=project,
        experiment=experiment,
        image=image,
        command_json=command_json,
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
    task.set_caching_options(False)
    task.set_cpu_request("100m").set_cpu_limit("500m")
    task.set_memory_request("256Mi").set_memory_limit("512Mi")
    kubernetes.add_node_selector(task, "environment", "cloud")
    kubernetes.add_node_selector(task, "kubernetes.io/arch", "amd64")
    kubernetes.use_config_map_as_env(
        task,
        config_map_name="kubeflow-artifact-env",
        config_map_key_to_env={
            "region": "AWS_REGION",
            "default-region": "AWS_DEFAULT_REGION",
            "endpoint-url": "AWS_ENDPOINT_URL",
            "endpoint-url-s3": "AWS_ENDPOINT_URL_S3",
            "ec2-metadata-disabled": "AWS_EC2_METADATA_DISABLED",
        },
    )
    kubernetes.use_secret_as_env(
        task,
        secret_name="kubeflow-artifact-store",
        secret_key_to_env={
            "accesskey": "AWS_ACCESS_KEY_ID",
            "secretkey": "AWS_SECRET_ACCESS_KEY",
        },
    )
    kubernetes.set_image_pull_policy(task, "IfNotPresent")
