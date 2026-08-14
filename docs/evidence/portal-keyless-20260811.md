# 접근 키 없는 연구자 포털 검증 — 2026-08-11

## 판정

PASS. ETRI/KIST 포털의 접근 키 입력 화면을 제거하고 Tenant별 자동 HttpOnly 세션을 배포했다. 직접 API와 MCP Token 인증은 유지한다.

## 배포 대상

- Image: `192.168.0.56:5000/mini-science-ai-os:0.2.8`
- Digest: `sha256:49503d356fce3b605da71fb327125fa55669d02892be966ae5d11d54a863cc59`
- ETRI: `http://192.168.0.56:8090/portal/`
- KIST: `http://192.168.0.56:8091/portal/`
- Binding: `0.0.0.0:8090`, `0.0.0.0:8091`

## HTTP 검증

```text
DIRECT_API=401
SESSION=200
COOKIE_FLAGS=science_portal_session_etri=<redacted>; HttpOnly; Max-Age=28800; Path=/; SameSite=strict
OWN_CONFIG=200
ETRI_SESSION_TO_KIST=401
COOKIE_POST_WITHOUT_ORIGIN=403
```

의미:

- 세션 없이 직접 API를 호출하면 401이다.
- 브라우저는 키를 받지 않고 8시간짜리 HttpOnly 세션만 받는다.
- ETRI 세션은 KIST API에서 사용할 수 없다.
- Cookie 기반 상태 변경은 Same-Origin 검사를 통과해야 한다.

## 브라우저 검증

새 Playwright Browser Context에서 `http://127.0.0.1:8090/portal/`을 열었다. 접근 키나 로그인 Form 없이 ETRI Dashboard가 바로 표시됐고 최초 정상 진입 Console Error는 0건이었다.

- Desktop Screenshot: `output/playwright/portal-etri-keyless-desktop.png`
- Mobile Screenshot: `output/playwright/portal-etri-keyless-mobile.png`

자동 세션만으로 다음 Job을 제출하고 취소했다.

```text
jobId=0ff837929e00
name=science-0ff837929e00
project=portal-keyless
experiment=keyless-session
kubeflowRunId=c5065f44-8d3c-4d2b-8188-c69967acd650
submit=PASS
cancel=PASS
GET after cancel=404 {"detail":"job not found"}
```

## 테스트

Unit/API Test 15건이 통과했다. 정적 검사에는 HTML/JavaScript에 `접근 키`, `tenant-api-token`, `sessionStorage`가 없는지 확인하는 항목이 포함된다. API Test에는 HttpOnly/SameSite Cookie, Cookie GET 허용, Origin 없는 Cookie DELETE 403이 포함된다.

```text
make validate: PASS
15 passed in 0.81s
Kustomize render: PASS
kubectl client validation: PASS
Security static checks: PASS
evidence: docs/evidence/validate-20260811T051512Z.md

make test: PASS
ETRI↔KIST RBAC deny: PASS
unauthenticated/direct cross-tenant API 401: PASS
disallowed image 400: PASS
privileged/hostPath input 422: PASS
MCP submit/status/cancel: PASS
evidence: docs/evidence/test-20260811T051546Z.md
```

KIST도 별도 새 Browser Context에서 확인했다.

```json
{"kist":true,"accessKey":false,"title":"Science AI Workspace"}
```

Console Error는 0건이었고 내부망 HTTP 응답은 ETRI/KIST 모두 200이었다. `ss -ltnp`에서 `0.0.0.0:8090`, `0.0.0.0:8091` 리스닝을 확인했다. 양쪽 Namespace의 `science-job-api`, `agent-runtime`은 모두 READY 1이며 `0.2.8` 이미지를 사용한다.

## 보안 제한

`PORTAL_ANONYMOUS_ACCESS=true`는 내부 데모 편의를 위한 설정이다. 현재는 URL에 접근 가능한 사람이 해당 Tenant 작업을 실행할 수 있다. Port Forward는 HTTP이므로 외부망에 공개하지 않는다. 운영 전 OIDC/TLS와 사용자별 권한을 적용해야 한다.
