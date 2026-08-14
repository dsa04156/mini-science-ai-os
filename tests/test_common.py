from __future__ import annotations

from science_os.common import parse_cpu_milli, parse_memory_bytes, sanitize


def test_quantity_parsing() -> None:
    assert parse_cpu_milli("500m") == 500
    assert parse_cpu_milli("2") == 2000
    assert parse_memory_bytes("4Gi") == 4 * 1024**3


def test_audit_sanitization() -> None:
    value = sanitize({"token": "secret", "datasetPath": "/sensitive/path", "nested": [{"password": "x"}]})
    assert value == {"token": "[REDACTED]", "datasetPath": "[REDACTED]", "nested": [{"password": "[REDACTED]"}]}

