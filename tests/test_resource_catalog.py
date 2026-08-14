from __future__ import annotations

import asyncio
from types import SimpleNamespace

from science_os.resource_catalog import _allocated_memory


class FakeCore:
    def __init__(self) -> None:
        self.pods = [
            SimpleNamespace(
                status=SimpleNamespace(phase="Running"),
                spec=SimpleNamespace(
                    containers=[SimpleNamespace(resources=SimpleNamespace(limits={"nvidia.com/gpumem": "1024"}, requests={}))]
                ),
            ),
            SimpleNamespace(
                status=SimpleNamespace(phase="Succeeded"),
                spec=SimpleNamespace(
                    containers=[SimpleNamespace(resources=SimpleNamespace(limits={"nvidia.com/gpumem": "4096"}, requests={}))]
                ),
            ),
        ]

    def list_pod_for_all_namespaces(self, *, field_selector: str):
        return SimpleNamespace(items=self.pods)


def test_allocated_memory_ignores_completed_pods() -> None:
    assert asyncio.run(_allocated_memory(FakeCore(), "gpu-node")) == 1024
