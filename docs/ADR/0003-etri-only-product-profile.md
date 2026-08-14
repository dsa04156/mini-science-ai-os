# ADR-0003: ETRI-only 제품 프로필

- 상태: Accepted
- 일자: 2026-08-11

## 맥락

초기 MVP는 단일 Cluster에서 ETRI와 KIST Namespace를 사용해 Tenant 격리를 검증했다. 제품 사용 범위가 ETRI 하나로 확정되어 KIST Runtime, Queue, 포털, Kubeflow Runner를 계속 운영할 이유가 없어졌다.

## 결정

- `clusters/lab`은 `tenant-etri`만 렌더링한다.
- LocalQueue와 Kubeflow Runner Identity도 ETRI만 유지한다.
- 프로젝트 소유권 Label을 확인하는 `remove-kist.sh`로 KIST Namespace를 제거하되 공유 KFP Metadata와 Object Storage는 보존한다.
- ETRI API/MCP는 2 Replica, Node anti-affinity와 PDB를 사용한다.
- Traefik Ingress `science-workspace.192.168.0.56.nip.io`를 안정적 내부 제품 URL로 사용한다.
- `VERSION=0.3.1`, `internal-production`/`trusted-network`, `/readyz`, API 문서 비공개, 내부망 IP Allowlist, Rate Limit, Security Header를 제품 기본값으로 둔다.

## 결과

- 사용자는 접근 키 없이 ETRI 워크스페이스 하나만 본다.
- KIST Namespace, LocalQueue, Runner Identity, 8091 Port Forward가 사라진다.
- 과거 KIST KFP Metadata/Artifact는 공유 저장소 보존 정책에 남는다.
- ETRI 내부망 사용은 READY로 판정한다. Flannel NetworkPolicy, local-path Storage, 미게시 GitOps는 내부 제품 운영 제약이며 외부 공개 시 별도 보강한다.
