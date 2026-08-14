from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from science_os import job_api


PORTAL = Path(job_api.__file__).with_name("portal")


def test_portal_assets_are_packaged_without_inline_executable_content() -> None:
    html = (PORTAL / "index.html").read_text(encoding="utf-8")
    javascript = (PORTAL / "portal.js").read_text(encoding="utf-8")

    assert '<script src="./portal.js" defer></script>' in html
    assert "<style" not in html
    assert "style=" not in html
    assert "localStorage" not in javascript
    assert "sessionStorage" not in javascript
    assert "접근 키" not in html
    assert "tenant-api-token" not in html


def test_portal_response_has_strict_browser_headers() -> None:
    client = TestClient(job_api.app)
    response = client.get("/portal/")

    assert response.status_code == 200
    assert "NAIS Science Workspace" in response.text
    assert response.headers["x-frame-options"] == "DENY"
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"


def test_portal_config_requires_tenant_token(monkeypatch: object) -> None:
    monkeypatch.setattr(job_api, "API_TOKEN", "test-tenant-token")
    monkeypatch.setenv("API_REQUIRE_TOKEN", "true")
    client = TestClient(job_api.app)

    denied = client.get("/v1/config")
    allowed = client.get("/v1/config", headers={"X-Science-Token": "test-tenant-token"})

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["namespace"] == job_api.TENANT_NAMESPACE
    assert allowed.json()["localQueue"] == job_api.LOCAL_QUEUE
    assert allowed.json()["defaultImage"].endswith(":0.3.1")
    assert allowed.json()["edition"] == "ETRI Internal"
    assert allowed.json()["version"] == "0.3.1"
    assert allowed.json()["deploymentProfile"] == "internal-production"


def test_product_root_redirects_and_readiness_is_etri_scoped(monkeypatch: object) -> None:
    monkeypatch.setattr(job_api, "API_TOKEN", "test-tenant-token")
    monkeypatch.setattr(job_api, "TENANT", "etri")
    monkeypatch.setattr(job_api, "TENANT_NAMESPACE", "tenant-etri")
    monkeypatch.setattr(job_api, "PORTAL_ACCESS_MODE", "trusted-network")
    client = TestClient(job_api.app)

    root = client.get("/", follow_redirects=False)
    ready = client.get("/readyz")

    assert root.status_code == 307
    assert root.headers["location"] == "/portal/"
    assert ready.status_code == 200
    assert ready.json()["version"] == "0.3.1"
    assert ready.json()["profile"] == "internal-production"
    assert ready.json()["accessMode"] == "trusted-network"
    assert ready.headers["x-request-id"]


def test_portal_creates_tenant_scoped_http_only_session(monkeypatch: object) -> None:
    monkeypatch.setattr(job_api, "API_TOKEN", "test-tenant-token")
    monkeypatch.setenv("API_REQUIRE_TOKEN", "true")
    monkeypatch.setattr(job_api, "PORTAL_ACCESS_MODE", "trusted-network")
    monkeypatch.delenv("PORTAL_ANONYMOUS_ACCESS", raising=False)
    client = TestClient(job_api.app)

    connected = client.post("/v1/portal/session")
    config = client.get("/v1/config")
    csrf_denied = client.delete("/v1/jobs/0123456789ab")

    assert connected.status_code == 200
    assert connected.json()["tenant"] == job_api.TENANT
    assert "HttpOnly" in connected.headers["set-cookie"]
    assert "SameSite=strict" in connected.headers["set-cookie"]
    assert job_api.PORTAL_COOKIE_NAME in client.cookies
    assert config.status_code == 200
    assert config.json()["tenant"] == job_api.TENANT
    assert csrf_denied.status_code == 403
