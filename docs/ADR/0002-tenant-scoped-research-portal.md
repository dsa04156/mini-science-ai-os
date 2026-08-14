# ADR-0002: ETRI API와 동일 Origin의 연구자 포털

- 상태: Accepted
- 일자: 2026-08-11

## 맥락

연구자는 Kubernetes Manifest나 Cluster 권한 없이 Science Job을 제출·관찰해야 한다. 제품 범위는 `tenant-etri` 하나이며 ETRI API Token, Science Job API, LocalQueue를 둔다.

## 결정

Science Job API가 `/portal/`에서 정적 UI를 제공한다. 실행 범위는 사용자 입력이 아니라 ETRI Deployment 환경과 Token으로 고정한다. 포털은 Kubernetes API를 직접 호출하지 않고 다음 ETRI API만 사용한다.

- `/v1/config`, `/v1/resources/summary`
- `/v1/jobs`, `/v1/jobs/{job_id}`
- `/v1/jobs/{job_id}/metrics`, `/v1/jobs/{job_id}/artifacts`

내부 데모에서는 접근 키 입력을 제거하고, 각 Tenant API가 자기 Tenant에만 유효한 HMAC 서명 HttpOnly Cookie를 자동 발급한다. Cookie 이름을 Tenant별로 분리하고 `SameSite=Strict`를 적용하며, Cookie로 인증된 상태 변경 요청에는 Same-Origin 검사를 요구한다. 직접 API와 MCP의 Token 인증은 유지한다. 외부 Script, Font, CDN을 사용하지 않고 CSP를 `self`로 제한한다.

## 결과

- KIST 배포 경로와 런타임 Identity를 제거하고 ETRI만 제품 Surface로 유지한다.
- Science Job API의 기존 Validation과 Audit 경로를 UI도 그대로 사용한다.
- 중앙 SSO와 통합 관리자 화면은 생기지 않는다.
- 현재 `0.0.0.0` Port Forward는 TLS가 없으므로 신뢰된 내부 데모망으로 제한한다.
- 익명 자동 세션은 내부 데모 편의 기능이며 URL 접근자가 Tenant 작업 권한을 갖는 위험을 수용한다.
- 운영 전 익명 자동 세션을 끄고 OIDC/PKCE, TLS, `Secure` Cookie, Ingress Rate Limit을 추가해야 한다.
