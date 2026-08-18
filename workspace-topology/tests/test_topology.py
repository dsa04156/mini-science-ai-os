from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

from science_os import job_api
from science_os.job_api import _mlflow_metric, _placement_for_job
from science_os.resource_catalog import _component_snapshot, _fleet_summary, _gpu_workload, _parse_hami_allocations


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


def test_fleet_summary_reports_real_capacity_and_architectures() -> None:
    nodes = [
        {
            "architecture": "amd64",
            "executionClass": "gpu",
            "health": "ready",
            "allocatable": {"cpu": "24", "memory": "32Gi"},
            "accelerator": {"model": "RTX Test"},
            "gpuDevices": [{"uuid": "GPU-a"}],
            "pressure": {"compute": 10.0, "memory": 40.0},
        },
        {
            "architecture": "arm64",
            "executionClass": "edge",
            "health": "ready",
            "allocatable": {"cpu": "4", "memory": "8Gi"},
            "accelerator": None,
            "gpuDevices": [],
            "pressure": {"compute": 20.0, "memory": 30.0},
        },
    ]

    result = _fleet_summary(nodes)

    assert result["readyNodeCount"] == 2
    assert result["cpuCores"] == 28.0
    assert result["memoryGiB"] == 40.0
    assert result["physicalGpuCount"] == 1
    assert result["architectures"] == {"amd64": 1, "arm64": 1}
    assert result["averageCpuPercent"] == 15.0


def test_component_snapshot_marks_replica_health() -> None:
    def metric(namespace: str, name: str, value: str, kind: str = "deployment") -> dict:
        return {"metric": {"namespace": namespace, kind: name}, "value": [0, value]}

    available = [
        metric("tenant-etri", "science-job-api", "2"),
        metric("tenant-etri", "agent-runtime", "1"),
    ]
    desired = [
        metric("tenant-etri", "science-job-api", "2"),
        metric("tenant-etri", "agent-runtime", "2"),
    ]
    stateful = [metric("science-ai-mlops", "minio", "1", "statefulset")]

    result = _component_snapshot(available, desired, stateful)
    by_name = {item["name"]: item for item in result}

    assert by_name["Science API"]["status"] == "ready"
    assert by_name["Agent Runtime"]["status"] == "degraded"
    assert by_name["Artifact Store"]["status"] == "ready"
    assert by_name["Kubeflow API"]["status"] == "unknown"
    assert by_name["MLflow"]["status"] == "unknown"
    assert by_name["Grafana"]["status"] == "unknown"


def test_mlflow_metric_reads_named_metric_without_guessing() -> None:
    run = {
        "data": {
            "metrics": [
                {"key": "samples", "value": 8},
                {"key": "mae", "value": 0.09},
            ]
        }
    }

    assert _mlflow_metric(run, "mae") == 0.09
    assert _mlflow_metric(run, "missing") is None


def test_portal_requests_operations_dashboard_data() -> None:
    portal = Path(job_api.__file__).with_name("portal")
    html = (portal / "index.html").read_text(encoding="utf-8")
    javascript = (portal / "portal.js").read_text(encoding="utf-8")
    stylesheet = (portal / "portal.css").read_text(encoding="utf-8")

    assert 'id="request-evidence-pipeline"' in html
    assert 'id="mlops-evidence"' in html
    assert 'id="gpu-telemetry"' in html
    assert "MLflow" in html
    assert "Grafana" in html
    assert 'api("/v1/operations")' in javascript
    assert "renderMlopsEvidence" in javascript
    assert 'replace("mlflow.192.168.0.56.nip.io", "mlflow.10.254.192.217.nip.io")' in javascript
    assert html.index('class="panel gpu-observatory"') < html.index('class="panel resource-panel"')
    assert html.index('class="panel resource-panel"') < html.index('class="panel platform-panel"')
    assert ".request-evidence-flow strong { color:#eef8f5; font-size:14px;" in stylesheet
    assert ".component-row strong { font-size:13px; }" in stylesheet
    assert re.search(r"\bETRI\b", html) is None
    assert "ETRI SCIENCE JOB" not in javascript
    assert "REQUEST-TO-EVIDENCE PIPELINE" in html
    assert "요청에서 실험 증거까지." in html
    assert "Metric · Artifact" in html
    assert html.index('id="mlops-evidence"') < html.index('id="request-evidence-pipeline"')
    assert 'id="fleet-strip"' in html
    assert 'byId("fleet-strip")' in javascript
    assert "publicIdentifier" in javascript
    assert "publicIdentifier(gpu?.node)" in javascript
