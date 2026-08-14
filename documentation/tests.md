# Product verification map

## Existing coverage

| Use case | Rule and expected deny | Evidence | Status |
|---|---|---|---|
| ETRI-only render | No KIST overlay, Queue or KFP identity | `tests/test_manifest_security.py`, Kustomize validation | existing |
| Portal session | HttpOnly/SameSite cookie; Origin-less write 403 | `tests/test_portal.py`, `scripts/test.sh` | existing |
| Product endpoint | `/` 307, `/portal/` 200, `/readyz` 200, version 0.3.1/internal-production/trusted-network | `tests/test_portal.py`, `scripts/test.sh` | existing |
| Unsafe request | privileged/hostPath extra fields 422 | `tests/test_job_api.py`, `scripts/test.sh` | existing |
| Image policy | non-allowlisted registry 400 | `tests/test_job_api.py`, `scripts/test.sh` | existing |
| Runner boundary | default Namespace Job create `no`; Secret read `no` | `scripts/test.sh` | existing guarded live |
| MCP lifecycle | submit/status/cancel and Streamable HTTP tools | `scripts/test.sh` | existing guarded live |
| Queue/GPU pipeline | Kueue state, KFP health, historic CPU/GPU evidence | `scripts/demo.sh`, `docs/evidence/` | existing guarded live |

CI is not connected because the workspace has no published Git repository. Therefore none of these currently gate merges to `main`; `make release-check` is the operator gate.

## Proposed tests

| Test | Type | Expected |
|---|---|---|
| OIDC login/logout/expiry and user audit subject | automated integration + guarded live | anonymous request denied, authenticated ETRI user allowed |
| TLS/HSTS and Secure cookie | guarded live | HTTP redirects; HTTPS cookie has Secure |
| NetworkPolicy cross-namespace and internet probes | guarded live | traffic denied by enforcing CNI |
| MinIO/MySQL backup restore | guarded live/manual review | known Run and Artifact restored |
| Replica disruption | guarded live | one API/MCP Pod eviction keeps endpoint available |
| Signed digest admission | automated integration | mutable/unsigned image denied |

## Gaps

| Priority | Unverified rule | Exposure |
|---|---|---|
| P1 | Per-user identity | 현재 승인 모델은 내부망 단위이며 개인별 감사 주체는 없음 |
| P1 | TLS transport | 내부망 평문 트래픽을 방어하지 않음 |
| P1 | NetworkPolicy enforcement | Manifest presence may not isolate traffic |
| P1 | Durable audit retention | Pod restart can remove local audit files; stdout retention is external |
| P1 | Storage restore and control-plane HA | Node/storage failure can lose availability or data |
| P1 | GitOps drift/recovery | Unpublished repository prevents Argo CD reconciliation proof |
