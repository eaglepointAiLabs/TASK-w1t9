# TablePay Static Audit Report

## 1. Verdict
- **Overall conclusion: Partial Pass**

## 2. Scope and Static Verification Boundary
- **Reviewed:** repository structure, docs, Flask entry points, routes/controllers/services/repositories/models, templates/static assets, Docker/test manifests, unit/API/frontend tests.
- **Not reviewed/executed:** runtime behavior, browser execution, Docker startup, DB migration execution, real callback simulator execution, backup/restore execution.
- **Intentionally not executed:** project startup, Docker, tests, external services (per audit constraints).
- **Manual verification required:** end-to-end runtime throughput/concurrency, actual offline restore on new machine, real browser UX behavior under load.

## 3. Repository / Requirement Mapping Summary
- **Prompt core goal mapped:** offline-first TablePay platform with SSR+HTMX customer flow, manager menu governance, finance payment/reconciliation/refund controls, community + moderation governance, and operational resilience.
- **Mapped implementation areas:** `backend/app/routes/*.py`, `backend/app/controllers/*.py`, `backend/app/services/*.py`, `backend/app/models/*.py`, `backend/app/templates/**/*.html`, `backend/app/static/js/htmx-lite.js`, `backend/app/static/css/app.css`, tests in `backend/*tests` and `frontend/*tests`.
- **Key constraints checked:** local auth with bcrypt + lockout + CSRF + nonce replay defense, callback signing + encrypted key storage + dedup window, partial/multi refunds + step-up, SQLite-backed jobs/rate-limit/circuit-breaker/backups.

## 4. Section-by-section Review

### 4.1 Hard Gates

#### 4.1.1 Documentation and static verifiability
- **Conclusion: Partial Pass**
- **Rationale:** startup/test instructions and architecture docs exist, but there are static inconsistencies that reduce reviewer confidence.
- **Evidence:** `README.md:44`, `repo/README.md:9`, `docs/api-spec.md:41`, `docs/design.md:14`, `README.md:76`, `backend/app/config.py:151`
- **Manual verification note:** runtime setup still needs manual check because docs cannot prove executable parity.

#### 4.1.2 Material deviation from prompt
- **Conclusion: Partial Pass**
- **Rationale:** implementation is strongly aligned to the prompt, but callback integrity binding has a security/semantic gap against payment callback trust expectations.
- **Evidence:** `backend/app/services/payment_service.py:76`, `backend/app/services/payment_service.py:187`, `docs/api-spec.md:238`

### 4.2 Delivery Completeness

#### 4.2.1 Coverage of explicit core requirements
- **Conclusion: Partial Pass**
- **Rationale:** most core modules are present (catalog/options, checkout, payments/callbacks/reconciliation, refunds/step-up, community/moderation, ops), but one high-risk callback validation gap remains.
- **Evidence:** `backend/app/routes/catalog.py:22`, `backend/app/routes/orders.py:23`, `backend/app/routes/payments.py:19`, `backend/app/routes/reconciliation.py:16`, `backend/app/routes/refunds.py:9`, `backend/app/routes/community.py:19`, `backend/app/routes/moderation.py:10`, `backend/app/routes/ops.py:8`

#### 4.2.2 End-to-end deliverable vs partial/demo
- **Conclusion: Pass**
- **Rationale:** full multi-module project structure, migrations, docs, SSR templates, static assets, and broad tests are present.
- **Evidence:** `README.md:5`, `repo/docker-compose.yml:1`, `repo/backend/migrations/versions/20260328_0009_ops.py`, `repo/backend/app/templates/base.html:1`, `repo/backend/API_tests/test_payment_api.py:1`

### 4.3 Engineering and Architecture Quality

#### 4.3.1 Module decomposition and structure
- **Conclusion: Pass**
- **Rationale:** clear layered architecture (`routes -> controllers -> services -> repositories -> models`) with coherent domain modules.
- **Evidence:** `docs/design.md:7`, `backend/app/factory.py:14`, `backend/app/routes/__init__.py:1`, `backend/app/models/__init__.py:1`

#### 4.3.2 Maintainability/extensibility
- **Conclusion: Partial Pass**
- **Rationale:** maintainable structure is strong; however, callback verification lacks strict field-binding checks and leaves extension-risk around payment integrity.
- **Evidence:** `backend/app/services/payment_service.py:187`, `backend/app/services/payment_service.py:213`, `backend/app/services/payment_service.py:78`

### 4.4 Engineering Details and Professionalism

#### 4.4.1 Error handling, logging, validation, API design
- **Conclusion: Partial Pass**
- **Rationale:** consistent `AppError` contract + sanitization + structured logging exist, but key payment callback validation is incomplete.
- **Evidence:** `backend/app/factory.py:101`, `backend/app/services/errors.py:56`, `backend/app/logging.py:9`, `backend/app/services/catalog_validation.py:52`, `backend/app/services/payment_service.py:186`

#### 4.4.2 Product/service-level organization
- **Conclusion: Pass**
- **Rationale:** codebase looks like a real service (roles, workspaces, ops, migration path, tests, docs), not a single-file demo.
- **Evidence:** `backend/app/templates/home/dashboard.html:3`, `backend/app/templates/finance/workspace.html:3`, `backend/app/templates/reconciliation/dashboard.html:3`, `backend/app/templates/moderation/queue.html:3`

### 4.5 Prompt Understanding and Requirement Fit

#### 4.5.1 Business goal and implicit constraint fit
- **Conclusion: Partial Pass**
- **Rationale:** broad fit is strong across ordering, finance, governance, and offline-oriented flows; one high-severity payment integrity miss and doc-to-code mismatches remain.
- **Evidence:** `backend/app/services/order_service.py:103`, `backend/app/services/refund_service.py:72`, `backend/app/services/reconciliation_service.py:59`, `backend/app/services/ops_service.py:182`, `backend/app/services/payment_service.py:187`, `docs/design.md:14`

### 4.6 Aesthetics (frontend-only/full-stack)

#### 4.6.1 Visual and interaction quality
- **Conclusion: Pass**
- **Rationale:** coherent visual system, responsive styles, clear role workspaces, and HTMX-like interaction feedback/toasts are statically present.
- **Evidence:** `backend/app/static/css/app.css:1`, `backend/app/static/css/app.css:452`, `backend/app/templates/base.html:17`, `backend/app/static/js/htmx-lite.js:92`, `backend/app/static/js/htmx-lite.js:165`
- **Manual verification note:** real browser smoothness/perceived responsiveness cannot be confirmed statically.

## 5. Issues / Suggestions (Severity-Rated)

### High
1) **Severity: High**
   - **Title:** Callback signature verification does not bind authoritative transaction reference
   - **Conclusion:** Fail
   - **Evidence:** `backend/app/services/payment_service.py:78`, `backend/app/services/payment_service.py:92`, `backend/app/services/payment_service.py:187`, `backend/app/services/payment_service.py:213`
   - **Impact:** a signed payload can be verified while import logic uses a different top-level `transaction_reference`, risking wrong transaction linkage/status mutation and breaking callback trust semantics.
   - **Minimum actionable fix:** enforce strict equality between `package.transaction_reference` and `package.payload.transaction_reference` before verification/import; reject mismatches with `400` and add test coverage.

### Medium
2) **Severity: Medium**
   - **Title:** Architecture/design docs contain non-existent path references
   - **Conclusion:** Partial Fail
   - **Evidence:** `docs/design.md:14`
   - **Impact:** static reviewers are directed to `fullstack/...` paths that do not exist in this repo, reducing verifiability and increasing audit confusion.
   - **Minimum actionable fix:** update docs to actual paths (`repo/backend/app/templates`, `repo/backend/app/static`, etc.).

3) **Severity: Medium**
   - **Title:** Root README configuration values are inconsistent with code
   - **Conclusion:** Partial Fail
   - **Evidence:** `README.md:76`, `backend/app/config.py:151`
   - **Impact:** README says `testing` while code expects `test`; setup guidance can fail or mislead reviewers.
   - **Minimum actionable fix:** align README env profile names and defaults with `CONFIG_BY_NAME` and real config behavior.

4) **Severity: Medium**
   - **Title:** Prompt-required pre-check UX for required options is only partially wired in UI
   - **Conclusion:** Partial Fail
   - **Evidence:** `docs/api-spec.md:118`, `backend/app/templates/partials/dish_detail.html:4`, `backend/app/controllers/catalog_controller.py:266`
   - **Impact:** endpoint exists for required-option selection checks, but dish detail form does not invoke it before add-to-cart/checkout flow; user guidance is less explicit than requested.
   - **Minimum actionable fix:** wire `selection-check` HTMX call from dish option changes and show inline required-option prompts before submit.

### Low
5) **Severity: Low**
   - **Title:** One backend API test file has stray trailing import statement
   - **Conclusion:** Partial Fail
   - **Evidence:** `backend/API_tests/test_ops_api.py:47`
   - **Impact:** reduces test-file professionalism and may trigger lint noise.
   - **Minimum actionable fix:** remove trailing unused import and enforce lint in CI.

## 6. Security Review Summary

- **Authentication entry points: Pass**
  - bcrypt login/register/session/lockout + CSRF enforcement are implemented.
  - Evidence: `backend/app/controllers/auth_controller.py:51`, `backend/app/services/auth_service.py:73`, `backend/app/services/auth_service.py:62`, `backend/app/factory.py:81`.

- **Route-level authorization: Partial Pass**
  - RBAC guards are present across manager/finance/moderation/ops flows.
  - Evidence: `backend/app/services/catalog_service.py:61`, `backend/app/services/payment_service.py:52`, `backend/app/services/reconciliation_service.py:35`, `backend/app/services/moderation_service.py:44`, `backend/app/controllers/ops_controller.py:17`.
  - Risk note: callback integrity validation issue remains (Issue #1).

- **Object-level authorization: Pass (scoped)**
  - user-order isolation enforced by `(order_id,user_id)` lookups.
  - user-block deletion is owner-scoped.
  - Evidence: `backend/app/repositories/order_repository.py:123`, `backend/app/services/order_service.py:185`, `backend/app/repositories/community_repository.py:90`.

- **Function-level authorization: Partial Pass**
  - nonce protection for refunds and role changes is implemented.
  - Evidence: `backend/app/services/refund_service.py:40`, `backend/app/services/refund_service.py:141`, `backend/app/services/moderation_service.py:117`.
  - Risk note: callback import verification lacks strict semantic binding (Issue #1).

- **Tenant / user data isolation: Partial Pass**
  - order isolation is explicit; no multi-tenant model exists (single local app). payment/refund/reconciliation are role-scoped, not owner-scoped by design.
  - Evidence: `backend/app/services/order_service.py:181`, `backend/app/services/payment_service.py:183`, `backend/app/services/refund_service.py:187`.

- **Admin / internal / debug protection: Pass**
  - ops/admin role-change endpoints require auth + finance role.
  - Evidence: `backend/app/controllers/ops_controller.py:17`, `backend/app/controllers/moderation_controller.py:96`, `backend/app/services/moderation_service.py:101`.

## 7. Tests and Logging Review

- **Unit tests: Pass (breadth), Partial (depth in key edge)**
  - broad unit coverage across auth/catalog/order/payment/refund/reconciliation/community/moderation/ops.
  - Evidence: `backend/unit_tests/test_auth_service.py:1`, `backend/unit_tests/test_payment_service.py:35`, `backend/unit_tests/test_ops_service.py:65`.

- **API / integration tests: Pass (breadth), Partial (specific gap)**
  - extensive API tests exist for major modules and auth/error contracts.
  - Evidence: `backend/API_tests/test_auth_api.py:9`, `backend/API_tests/test_payment_api.py:120`, `backend/API_tests/test_refund_api.py:28`, `backend/API_tests/test_error_contract_api.py:4`.
  - Gap: no test for mismatched package-level vs payload-level callback transaction reference.

- **Logging categories / observability: Pass**
  - structured JSON logs + request context + categorized domain events are present.
  - Evidence: `backend/app/logging.py:9`, `backend/app/factory.py:66`, `backend/app/services/refund_service.py:128`, `backend/app/services/ops_service.py:84`.

- **Sensitive-data leakage risk in logs/responses: Partial Pass**
  - sanitizer redacts sensitive detail keys and tests assert redaction.
  - Evidence: `backend/app/services/errors.py:17`, `backend/unit_tests/test_error_sanitization.py:37`.
  - Remaining risk: integrity issue in callback semantic validation (not direct leakage, but trust/control risk).

## 8. Test Coverage Assessment (Static Audit)

### 8.1 Test Overview
- Unit tests exist under `backend/unit_tests` and `frontend/unit_tests` using pytest.
- API/integration-style tests exist under `backend/API_tests` and `frontend/API_tests`.
- E2E tests exist under `frontend/e2e` and require live runtime (skippable if unavailable).
- Test commands are documented in both READMEs.
- Evidence: `backend/pyproject.toml:12`, `repo/README.md:28`, `README.md:83`, `frontend/e2e/conftest.py:21`.

### 8.2 Coverage Mapping Table

| Requirement / Risk Point | Mapped Test Case(s) | Key Assertion / Fixture / Mock | Coverage Assessment | Gap | Minimum Test Addition |
|---|---|---|---|---|---|
| Auth + lockout + password policy + CSRF | `backend/API_tests/test_auth_api.py:9`, `backend/unit_tests/test_auth_service.py:45` | lockout 423, csrf 403, password policy rejection | sufficient | none major | n/a |
| SSR + role page boundaries | `frontend/API_tests/test_ssr_routes.py:74` | customer gets 403 on finance/manager/moderation pages | basically covered | runtime UX cannot be proven | add browser assertion for visible nav/denied states |
| Catalog required options + image validation | `backend/API_tests/test_catalog_api.py:94`, `backend/API_tests/test_catalog_api.py:111` | `required_options_missing`, invalid type/size | basically covered | pre-check UX not asserted | add HTMX UI test for selection-check prompt rendering |
| Checkout idempotency + concurrency/oversell | `backend/unit_tests/test_order_service.py:14`, `backend/unit_tests/test_order_service.py:30` | same key returns same order; race yields one success | sufficient | runtime perf thresholds not proven | add benchmark/perf regression test guidance |
| Callback signature verification + dedup | `backend/API_tests/test_payment_api.py:120`, `backend/unit_tests/test_payment_service.py:97` | duplicate import same callback id; invalid signature rejected | basically covered | **reference-binding mismatch untested** | add failing test for `package.transaction_reference != payload.transaction_reference` |
| Refund nonce + step-up governance | `backend/API_tests/test_refund_api.py:28`, `backend/unit_tests/test_refund_service.py:63` | high-risk pending_stepup; manager approval required | sufficient | none major | n/a |
| Reconciliation import/exceptions/resolve + async jobs | `backend/API_tests/test_reconciliation_api.py:53`, `backend/unit_tests/test_ops_service.py:65` | import/run ids, exception resolution, queued job completes | sufficient | CSV edge fuzzing limited | add malformed CSV row and huge-file boundary tests |
| Community throttle/cooldown/block | `backend/unit_tests/test_community_service.py:24`, `backend/API_tests/test_community_api.py:122` | cooldown/throttle and auth checks | basically covered | dish-target interaction paths thin | add API tests for `target_type="dish"` like/comment/report |
| Admin role governance nonce and privilege checks | `backend/API_tests/test_moderation_api.py:72`, `backend/unit_tests/test_moderation_service.py:34` | nonce required; moderator forbidden | sufficient | none major | n/a |
| Backup/restore/rate-limit/circuit-breaker | `backend/API_tests/test_ops_api.py:18`, `backend/unit_tests/test_ops_service.py:48` | backup/restore paths, rate/circuit behavior | basically covered | full machine-rebuild offline restore unproven | add documented manual restore drill assertion script |

### 8.3 Security Coverage Audit
- **authentication:** covered meaningfully (login/register/logout/me + lockout + CSRF) with API + unit tests.
- **route authorization:** covered for major privileged surfaces (`manager`, `finance`, `moderator`, `ops`) via SSR/API tests.
- **object-level authorization:** covered for orders and user block ownership; limited explicit coverage for some finance datasets (role-scoped by design).
- **tenant/data isolation:** no tenant model; user isolation checks exist mainly for orders and sessions.
- **admin/internal protection:** covered for role changes and ops endpoints (auth+RBAC+nonce where applicable).
- **Severe undetected-risk potential:** callback transaction-reference binding defect currently not covered by tests and could bypass intended callback trust semantics.

### 8.4 Final Coverage Judgment
- **Partial Pass**
- Major core paths are covered statically by tests, but uncovered callback semantic-binding risk means tests could still pass while a severe payment-integrity defect remains.

## 9. Final Notes
- This audit is static-only and evidence-based; no runtime execution claims are made.
- The codebase is substantial and largely aligned to the prompt.
- Priority fix should be callback reference-binding validation + regression tests, then documentation consistency cleanup.
