# Security decisions

| ID | 결정 | 검증/제한 |
|---|---|---|
| SEC-001 | ETRI API Token과 `tenant-etri` 고정 Deployment | Token은 Git에 저장하지 않음. 중앙 SSO는 향후 범위 |
| SEC-002 | 요청에서 Namespace/PodSpec을 받지 않고 검증된 KFP Parameter만 생성 | `extra=forbid`, privileged/hostPath/hostPID/hostNetwork 입력 422 |
| SEC-003 | Command는 `list[str]`만 허용 | Shell 문자열 해석 없음 |
| SEC-004 | Image Registry Allowlist와 Tenant 자원 상한 | 운영은 Digest 필수 설정 권장 |
| SEC-005 | Job/Agent는 non-root, RuntimeDefault, drop ALL, read-only rootfs, 제한된 tmpfs | Host access 금지 |
| SEC-006 | KFP Runner SA는 ETRI Job/Pod/Workload만 조작 | default Namespace Job 생성과 Secret 조회 거부 |
| SEC-007 | MCP는 Science Job API/Catalog만 호출 | Kubernetes Client·Token 없음, Tool Audit JSON 기록 |
| SEC-008 | Default Deny와 허용 경로 NetworkPolicy 제공 | 현재 Flannel에서 실제 Enforcement는 BLOCKED |
| SEC-009 | MinIO/MySQL/API Token은 Secret Ref | `ensure-secrets.sh`가 값을 출력하지 않고 생성/보존 |
| SEC-010 | 기존 HAMi/Prometheus/Grafana/Argo/KubeEdge를 수정하지 않음 | 프로젝트 Namespace·Label 범위만 사용 |
| SEC-011 | Kaniko는 Build Namespace에서만 최소 Capability 사용 | Runtime Tenant Pod는 계속 drop ALL |
| SEC-012 | KFP UI/API는 ClusterIP, 사용자 인증 없음 | Admin Port Forward만 허용. 운영 전 OIDC/Proxy 필요 |
| SEC-013 | ETRI 내부 제품은 `trusted-network` 동일 Origin 자동 HttpOnly 세션 사용 | `192.168.0.0/24` Ingress Allowlist, 8시간 만료, SameSite=Strict, 상태 변경 Same-Origin 검사 |
| SEC-014 | 포털 정적 자원은 외부 CDN/Script 없이 패키징 | `script-src/style-src/connect-src 'self'`, frame 차단, no-referrer, nosniff 적용 |

## Trust boundary

실행 범위는 HTTP Body가 아니라 API Deployment의 `TENANT_NAMESPACE=tenant-etri`와 Token Secret으로 결정된다. API는 KFP Run을 제출하며 KFP는 `pipeline-runner-etri` ServiceAccount를 사용한다. 요청자는 ServiceAccount, Volume, SecurityContext, Namespace를 선택할 수 없다.

KFP Standalone API 자체에는 최종 사용자 인증이 없으므로 외부 Ingress로 공개하지 않는다. 연구자/Agent는 Tenant Science API만 사용한다. UI의 `0.0.0.0` Port Forward는 내부 데모용이며 TLS·인증을 추가하기 전 외부망 공개가 금지된다.

연구자 포털은 API Token을 브라우저로 전달하지 않는다. ETRI API가 HMAC 서명 세션을 자동 발급하며 Cookie는 JavaScript에서 읽을 수 없다. Origin 없는 상태 변경 요청은 403이다.

현재 `PORTAL_ACCESS_MODE=trusted-network`는 ETRI 내부망을 하나의 신뢰 경계로 취급한다. Traefik IP Allowlist를 통과한 사용자는 별도 키 입력 없이 ETRI 작업을 실행할 수 있다. 이는 내부 운영 제품의 승인된 접근 모델이다. 사용자별 실명 감사나 외부 공개가 필요해질 때 OIDC/TLS를 추가한다.

## GPU 경계

HAMi `nvidia.com/gpumem`, `nvidia.com/gpucores`는 논리 Scheduling 값이다. Memory Bandwidth, Cache, Thermal/Power, Kernel 간섭이 같은 비율로 격리된다고 가정하지 않는다. HAMi Annotation과 DCGM Metric을 함께 기록한다.

## BLOCKED

Calico/Cilium/Antrea/OVN 정책 Controller가 확인되지 않았다. NetworkPolicy Object 생성은 완료했지만 Cross-Tenant 및 외부 Network 차단의 실제 Enforcement는 검증되지 않았다.
