# 보안 검토 결과

## 요약

FastAPI, Vanilla JavaScript, Kubernetes Manifest와 MLOps/운영 훈련 경로를
검토했다. 확인된 Critical/High 취약점은 없다. 기존 제품 문서가 이미 공개한
두 개의 Medium 운영 위험과 두 개의 Low 방어 심층화 항목이 남는다.

## Medium

### SEC-PORT-001 — NetworkPolicy 강제 여부 미검증

- 위치: `docs/security-decisions.md:36`, `docs/evidence/verification-matrix.md`
- 증거: Flannel은 관찰됐지만 Calico/Cilium/Antrea/OVN Policy Controller는
  확인되지 않았다.
- 영향: Manifest가 존재해도 Pod 간 통신 차단이 실제로 적용되지 않을 수 있다.
- 수정: Policy Engine이 있는 CNI를 도입하고 Cross-Namespace 및 외부 Egress
  Negative Probe를 Release Gate에 추가한다.
- 완화: Ingress IP Allowlist, Namespace RBAC, Agent의 Kubernetes Credential 제거를
  유지한다.
- 오탐 확인: 별도 Policy Controller가 클러스터 외부 방식으로 설치됐는지 확인한다.

### SEC-PORT-002 — 내부망 단위 Portal Identity

- 위치: `services/science_os/job_api.py:479`, `tenants/etri/product.yaml:32`
- 증거: 신뢰된 네트워크 요청은 사용자 인증 없이 ETRI Scope의 서명 Cookie를 받는다.
- 영향: 허용된 내부망의 서로 다른 사용자를 구별하거나 사용자별 권한·감사 주체를
  제공할 수 없다.
- 수정: TLS 뒤에 OIDC를 연결하고 `sub`, Group, Tenant Claim을 Server-side
  Session과 Audit Subject로 사용한다.
- 완화: Cookie는 HttpOnly/SameSite Strict이며 쓰기 요청에 Same-Origin 검사를
  적용하고, Ingress Allowlist와 Rate Limit을 사용한다.
- 오탐 확인: 기관망 상단 Proxy에서 개인 Identity를 이미 강제하는지 확인한다.

## Low

### SEC-PORT-003 — 애플리케이션 Host Allowlist 부재

- 위치: `services/science_os/job_api.py:51`, `services/science_os/job_api.py:148`
- 증거: 앱에는 `TrustedHostMiddleware`가 없고 CSRF 예상 Origin 계산에 요청 Host를
  사용한다.
- 영향: Service가 Ingress 외 경로로 노출되면 Host 기반 Origin 판단의 신뢰 경계가
  넓어질 수 있다.
- 수정: 배포 Host 목록을 환경 변수로 주입해 `TrustedHostMiddleware`로 제한한다.
- 완화: 현재 Traefik Ingress는 고정 Host Rule과 내부 IP Allowlist를 사용한다.
- 오탐 확인: Traefik이 알 수 없는 Host를 항상 거부하는지 Runtime Test로 확인한다.

### SEC-DOCS-001 — 정적 문서 CSP의 unsafe-inline

- 위치: `open-source-docs/workload.yaml:128`
- 증거: 정적 문서 CSP가 `style-src`와 `script-src`에 `unsafe-inline`을 허용한다.
- 영향: 향후 문서에 사용자 제어 콘텐츠가 들어오면 CSP의 XSS 완화 효과가 약해진다.
- 수정: Inline Script/Style을 동일 Origin 파일로 분리하고 `script-src 'self'`로
  제한한다.
- 완화: 문서는 고정 정적 콘텐츠이며 `object-src/base-uri/frame-ancestors`를
  차단하고 내부망에서만 제공한다.
- 오탐 확인: 현재 문서 Build 과정에 사용자 제어 Markdown/HTML이 없는지 확인한다.

## 확인된 안전 기본값

- Pydantic Write Model은 Extra Field를 거부한다.
- Production Profile에서 OpenAPI/Docs가 비활성화된다.
- Portal Cookie는 HttpOnly, SameSite Strict이며 Secure Flag는 TLS 여부로 분리된다.
- Portal CSP, Referrer Policy, NoSniff, Frame Deny가 설정된다.
- MLflow는 non-root, capability drop, RuntimeDefault seccomp와 내부망 Ingress를 사용한다.
- 새 복구 훈련은 Source DB/PVC에 Restore하지 않고 고정 격리 Namespace만 사용한다.

## 이번 작업에서 해결한 항목

- `pip-audit`가 `pytest 8.4.2`의 `PYSEC-2026-1845`를 탐지해 개발 의존성을
  수정 버전 `9.0.3`으로 올렸다.
- 갱신 후 제품·포트폴리오 테스트와 Runtime/Development 의존성 감사를
  다시 실행하는 CI Gate를 추가했다.
