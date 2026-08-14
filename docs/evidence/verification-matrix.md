# Verification matrix

이 표는 실제 명령의 evidence 파일과 함께 갱신합니다. Manifest/코드가 존재하는 것만으로 PASS로 표시하지 않습니다.

| 흐름 | 구현 위치 | 실제 검증 기준 | 현재 상태 |
|---|---|---|---|
| Phase 0 inventory | `docs/inventory.md`, `scripts/inventory.sh` | Kubernetes/KubeEdge/HAMi/Prometheus/Storage/Argo 조회 출력 | PASS (클러스터 조회 완료) |
| ETRI Namespace and PSA | `tenants/etri`, `policies/namespaces.yaml` | namespace labels, quota, limit range, API rollout, KIST absence | PASS; ETRI API/MCP 2/2 Ready, KIST Namespace absent |
| ETRI least privilege | `tenants/base/rbac.yaml`, `scripts/test.sh` | Agent direct Job/Pod/Secret, API Secret, Runner default Job denied | PASS; five `kubectl auth can-i` checks returned `no` |
| Kueue queue | `apps/kueue/queues.yaml` | CRD/controller, ClusterQueue/LocalQueue status, Workload pending reason | PASS; 3 CPU 사용 중 6 CPU 요청이 `insufficient unused quota ... 1 more needed`, 정리 후 입장 가능 |
| HAMi logical GPU | API resource env and GPU demo | Pod uses discovered resources and `hami-scheduler`; DCGM snapshot | PASS; 두 0.2.4 Job이 동일 GPU UUID에 1024MiB/10%씩 할당. 물리 QoS는 주장하지 않음 |
| Resource Catalog | `services/science_os/resource_catalog.py` | `/v1/sites`, `/v1/nodes`, `/v1/resources`, `/v1/resources/summary` from live Node/Prometheus | PASS; 5 nodes/2 GPU nodes and discovered resource names returned |
| Kubeflow/MySQL/MinIO | `apps/kubeflow/*`, `apps/mlops/minio.yaml` | KFP health, Workflow, Run/Metric/Artifact readback | PASS; KFP 2.17.0, 0.2.4 CPU/GPU Runs, MySQL/MinIO Ready |
| Science Job API | `services/science_os/job_api.py` | token, allowlist, validation, KFP Run create/list/delete | PASS; 401/400/422 및 실제 KFP Run create/read/delete |
| ETRI Product Portal | `services/science_os/portal/*`, `tenants/etri/product.yaml` | stable Ingress, auto session, internal IP allowlist, submit/cancel, responsive browser | PASS; 0.3.1 trusted-network Ingress, Job `efbb4d3e53ed` submit/cancel, desktop/mobile, console error 0 |
| MCP tools and audit | `services/science_os/mcp_server.py` | required tool list, self-scope lifecycle, JSON log | PASS; 6 Tools, Job `21b1a3d27e52` submit/status/cancel와 linked_job_id Audit |
| Product availability | `tenants/etri/*availability*`, `product.yaml` | API/MCP 2 replicas on separate Nodes, PDB, readiness | PASS; each 2/2 Ready across both Cloud Nodes, PDB allowed disruption 1 |
| Internal product release | `scripts/release-check.sh`, `scripts/product-status.sh` | version/profile/access mode, endpoint, runtime, browser | READY; `VERSION=0.3.1`, `internal-production`, `trusted-network`, `INTERNAL_PRODUCT=READY` |
| NetworkPolicy enforcement | tenant/system policy manifests | CNI policy engine and cross-namespace/external deny probe | DEFERRED hardening; Flannel-only라 Pod NetworkPolicy enforcement 미검증. 내부 제품 Ingress는 Traefik IP allowlist 적용 |
| Grafana/alerts | JSON + PrometheusRule | Kubeflow/MinIO/Kueue/GPU/API/MCP Rules, dashboard import | PARTIAL; Rule Manifest 적용, Grafana UI Import는 미검증 |
| Argo App-of-Apps | `argocd/*` | three Applications Synced/Healthy | BLOCKED; Manifest 작성 완료, 게시 Git URL이 없어 Application 미생성 |
