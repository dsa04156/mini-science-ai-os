from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_new_workloads_do_not_request_host_or_privileged_access() -> None:
    paths = [ROOT / "tenants", ROOT / "apps" / "resource-catalog", ROOT / "apps" / "mlops", ROOT / "workloads"]
    text = "\n".join(path.read_text(encoding="utf-8") for root in paths for path in root.rglob("*.yaml"))
    assert "privileged: true" not in text
    assert "hostPID: true" not in text
    assert "hostNetwork: true" not in text
    assert "hostPath:" not in text


def test_secrets_are_referenced_not_committed_as_real_values() -> None:
    for path in (ROOT / "tenants").rglob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        assert "REPLACED_BY_SCRIPTS_ENSURE_SECRETS" not in text or path.name == "secret-placeholder.yaml"
    storage = "\n".join(
        (ROOT / "apps" / "mlops" / name).read_text(encoding="utf-8")
        for name in ("minio.yaml",)
    )
    kubeflow = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "apps" / "kubeflow").rglob("*.yaml")
    )
    assert "secretKeyRef:" in storage
    assert "secretKeyRef:" in kubeflow
    assert "platform-minio" in storage


def test_product_overlay_is_etri_only_and_has_availability_controls() -> None:
    cluster = (ROOT / "clusters" / "lab" / "kustomization.yaml").read_text(encoding="utf-8")
    queues = (ROOT / "apps" / "kueue" / "queues.yaml").read_text(encoding="utf-8")
    launchers = (ROOT / "apps" / "kubeflow" / "tenant-launchers" / "rbac.yaml").read_text(encoding="utf-8")
    product = (ROOT / "tenants" / "etri" / "product.yaml").read_text(encoding="utf-8")
    availability = "\n".join(
        (ROOT / "tenants" / "etri" / name).read_text(encoding="utf-8")
        for name in ("science-job-api-availability-patch.yaml", "agent-runtime-availability-patch.yaml")
    )

    assert "tenant-kist" not in cluster
    assert "tenant-kist" not in queues
    assert "pipeline-runner-kist" not in launchers
    assert not (ROOT / "tenants" / "kist").exists()
    assert "kind: PodDisruptionBudget" in product
    assert "kind: Ingress" in product
    assert "kind: Middleware" in product
    assert "ipAllowList:" in product
    assert "192.168.0.0/24" in product
    assert availability.count("replicas: 2") == 2
