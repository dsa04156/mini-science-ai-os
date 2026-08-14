from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_os.job_api import ScienceJobRequest, _check_image, _check_resources, build_job


def request(**overrides: object) -> ScienceJobRequest:
    value: dict[str, object] = {
        "project": "physical-ai",
        "image": "192.168.0.56:5000/mini-science-ai-os:0.3.1",
        "command": ["python", "-m", "science_os.demo", "--mode", "cpu"],
        "resources": {"cpu": "500m", "memory": "512Mi"},
        "datasetVersion": "factory-v1",
        "experiment": "defect-detection",
        "priority": "normal",
    }
    value.update(overrides)
    return ScienceJobRequest.model_validate(value)


def test_valid_request_rejects_extra_privileged_field() -> None:
    with pytest.raises(ValidationError):
        request(privileged=True)


def test_command_is_array_and_image_is_allowlisted() -> None:
    _check_image("192.168.0.56:5000/approved/image:1")
    with pytest.raises(Exception):
        _check_image("evil.example.invalid/image:1")


def test_gpu_resources_use_discovered_hami_names() -> None:
    job = build_job(
        "0123456789ab",
        request(
        image="192.168.0.56:5000/mini-science-ai-os:0.3.1",
            resources={
                "cpu": "500m",
                "memory": "512Mi",
                "acceleratorVendor": "nvidia",
                "gpuCount": 1,
                "gpuMemoryMiB": 1024,
                "gpuCorePercent": 10,
            },
        ),
    )
    container = job.spec.template.spec.containers[0]
    assert container.resources.limits["nvidia.com/gpu"] == "1"
    assert container.resources.limits["nvidia.com/gpumem"] == "1024"
    assert container.resources.limits["nvidia.com/gpucores"] == "10"
    assert job.spec.template.spec.scheduler_name == "hami-scheduler"


def test_resource_limits_are_checked_before_kubernetes() -> None:
    with pytest.raises(Exception):
        _check_resources(request(resources={"cpu": "9", "memory": "1Gi"}).resources)
