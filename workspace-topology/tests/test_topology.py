from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from science_os import job_api
from science_os.job_api import _placement_for_job
from science_os.resource_catalog import _gpu_workload, _parse_hami_allocations


def test_hami_allocation_parser_keeps_uuid_memory_and_core() -> None:
    devices = {"GPU-abc": {"model": "RTX Test"}}
    result = _parse_hami_allocations(";GPU-abc,NVIDIA,1024,10:;", devices)

    assert result == [
        {
            "uuid": "GPU-abc",
            "vendor": "NVIDIA",
            "model": "RTX Test",
            "memoryMiB": 1024,
            "corePercent": 10,
        }
    ]


def test_gpu_workload_marks_completed_allocation_as_released() -> None:
    pod = SimpleNamespace(
        metadata=SimpleNamespace(
            name="science-0123456789ab-pod",
            namespace="tenant-etri",
            labels={"science-ai.io/job-id": "0123456789ab", "science-ai.io/tenant": "etri"},
            annotations={"hami.io/vgpu-devices-allocated": "GPU-abc,NVIDIA,1024,10:;"},
            owner_references=[],
        ),
        spec=SimpleNamespace(
            node_name="gpu-node",
            containers=[
                SimpleNamespace(
                    resources=SimpleNamespace(
                        limits={"nvidia.com/gpu": "1", "nvidia.com/gpumem": "1024", "nvidia.com/gpucores": "10"},
                        requests={},
                    )
                )
            ],
        ),
        status=SimpleNamespace(phase="Succeeded"),
    )

    result = _gpu_workload(pod, {"GPU-abc": {"model": "RTX Test"}})

    assert result is not None
    assert result["active"] is False
    assert result["node"] == "gpu-node"
    assert result["allocations"][0]["uuid"] == "GPU-abc"


def test_job_placement_joins_topology_by_science_job_id() -> None:
    topology = {
        "sites": [
            {
                "site": "etri-lab",
                "nodes": [
                    {
                        "node": "gpu-node",
                        "health": "ready",
                        "accelerator": {"model": "RTX Test"},
                        "gpuWorkloads": [
                            {
                                "jobId": "0123456789ab",
                                "pod": "science-pod",
                                "phase": "Running",
                                "active": True,
                                "allocations": [{"uuid": "GPU-abc", "memoryMiB": 1024, "corePercent": 10}],
                            }
                        ],
                    }
                ],
            }
        ]
    }

    result = _placement_for_job(topology, "0123456789ab")

    assert result is not None
    assert result["site"] == "etri-lab"
    assert result["node"] == "gpu-node"
    assert result["allocations"][0]["uuid"] == "GPU-abc"


def test_service_home_uses_the_live_research_hub() -> None:
    portal = Path(job_api.__file__).with_name("portal")
    html = (portal / "index.html").read_text(encoding="utf-8")
    javascript = (portal / "portal.js").read_text(encoding="utf-8")

    assert "http://research-hub.192.168.0.56.nip.io/" in html
    assert "nais.192.168.0.56.nip.io" not in html
    assert '"research-hub.192.168.0.56.nip.io", "research-hub.10.254.192.217.nip.io"' in javascript
