# Disaster recovery

## 현재 한계

KFP MySQL과 MinIO PVC는 `local-path`이며 PV Reclaim Policy는 `Delete`다. 원격 Backup Controller나 외부 Object Storage가 발견되지 않았으므로 이 MVP는 재해복구 완료를 주장하지 않는다.

## 복구 가능한 범위

- Git Manifest로 Kueue, KFP, API, Catalog, MCP, Policy를 재생성할 수 있다.
- MySQL Run/Metadata와 MinIO Artifact는 해당 Node/PVC가 살아 있을 때만 복구 가능하다.
- Secret은 Git에 없으므로 승인된 외부 저장소에서 복원해야 한다.
- 교체 이전 PostgreSQL PVC `data-postgres-0`은 마이그레이션 안전망으로 삭제하지 않았지만 현재 Runtime에서는 사용하지 않는다.

## 운영 전 필수 절차

1. MySQL Point-in-time Backup과 Clean Namespace Restore를 시험한다.
2. MinIO Versioning/Replication 또는 외부 S3 Bucket을 구성한다.
3. KFP Run ID, Image Digest, Dataset Version, Artifact URI 목록을 Export한다.
4. Secret은 External Secret Manager로 Backup한다.
5. RPO/RTO와 Tenant 단위 Restore Drill을 문서화한다.

안전한 복구 순서는 `StorageClass/외부 저장소 → Secret → MySQL/MinIO → KFP → API/MCP/Catalog → Kueue/Policy → CPU Demo`다. 일반 Rollback과 장애 조사 중에는 PVC를 삭제하지 않는다.
