from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SiteNode:
    site: str
    node: str
    architecture: str | None
    execution_class: str | None
    accelerator: dict[str, Any] | None
    health: str


class SiteAdapter(ABC):
    """Stable adapter boundary for future independent sites or schedulers."""

    @abstractmethod
    async def list_nodes(self) -> list[SiteNode]:
        raise NotImplementedError


class KubernetesSiteAdapter(SiteAdapter):
    """Implemented by the Resource Catalog using the Kubernetes API and Prometheus."""

    async def list_nodes(self) -> list[SiteNode]:  # pragma: no cover - implemented by catalog service
        raise NotImplementedError("Catalog injects the Kubernetes observation implementation")


class SlurmSiteAdapter(SiteAdapter):
    """Interface plus deterministic mock; real SLURM integration is out of MVP scope."""

    def __init__(self, mock_nodes: list[SiteNode] | None = None) -> None:
        self.mock_nodes = mock_nodes or []

    async def list_nodes(self) -> list[SiteNode]:
        return list(self.mock_nodes)


class CloudSiteAdapter(SiteAdapter):
    """Future interface for a cloud provider; no cloud control-plane calls in MVP."""

    async def list_nodes(self) -> list[SiteNode]:
        raise NotImplementedError("CloudSiteAdapter is an extension interface only")

