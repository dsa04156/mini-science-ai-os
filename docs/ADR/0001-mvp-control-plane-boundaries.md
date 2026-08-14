# ADR-0001: MVP control-plane boundaries

Status: accepted

## Context

The existing cluster already contains HAMi, KubeEdge, Prometheus/Grafana/DCGM, Argo CD and a State Aggregator. Replacing or reconfiguring these shared components would create unnecessary outage risk. The MVP needs a verifiable Science Job flow without inventing a scheduler or federation protocol.

## Decision

Use standard Kubernetes Jobs, Kueue v0.17.3, the existing kube-scheduler, and the existing HAMi resource names discovered from the live ConfigMap. Deploy new components only into project namespaces. Put a narrow FastAPI API and tenant MCP server in each tenant namespace. Use adapter interfaces for future Kubernetes/SLURM/cloud sites.

## Consequences

This provides a small, inspectable control plane and preserves existing workloads. It does not provide central SSO, network isolation when the CNI lacks a policy engine, physical GPU QoS isolation, multi-cluster scheduling, or durable DR. Those limitations are explicit in the threat model and verification matrix.

