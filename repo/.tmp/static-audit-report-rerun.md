# TablePay Static Audit Report (Re-test)

## 1. Verdict
- **Overall conclusion: Partial Pass**

## 2. Scope and Static Verification Boundary
- **Reviewed:** changed files plus impacted paths: callback security logic/tests, docs, dish selection template, JS enhancement layer, ops/payment tests.
- **Not reviewed/executed:** runtime startup, Docker, test execution, browser behavior, external services.
- **Intentionally not executed:** app/tests/docker (per static-only instruction).
- **Manual verification required:** runtime UI behavior for newly added option pre-check interaction.

## 3. Repository / Requirement Mapping Summary
- Re-mapped prior findings to current code in `backend/app/services/payment_service.py`, `backend/API_tests/test_payment_api.py`, `backend/unit_tests/test_payment_service.py`, `docs/design.md`, `README.md`, and `backend/app/templates/partials/dish_detail.html`.
- Focused on previously reported High/Medium root causes and regression risk.

## 4. Section-by-section Review

### 4.1 Hard Gates

#### 4.1.1 Documentation and static verifiability
- **Conclusion: Partial Pass**
- **Rationale:** previously reported config/profile mismatch and bad path references are fixed; however new README test-run instructions now overstate script location/capabilities.
- **Evidence:** `README.md:76`, `README.md:85`, `README.md:90`, `README.md:98`, `repo/run_tests.sh:1`, `docs/design.md:14`

#### 4.1.2 Material deviation from prompt
- **Conclusion: Pass**
- **Rationale:** payment callback reference-binding defect previously reported is now addressed with explicit validation.
- **Evidence:** `backend/app/services/payment_service.py:81`, `backend/app/services/payment_service.py:225`

### 4.2 Delivery Completeness

#### 4.2.1 Coverage of explicit core requirements
- **Conclusion: Partial Pass**
- **Rationale:** payment integrity fix is implemented and tested, but required-option pre-check UX remains statically incomplete because enhancement layer does not execute non-form `hx-post` elements.
- **Evidence:** `backend/app/templates/partials/dish_detail.html:12`, `backend/app/static/js/htmx-lite.js:167`, `backend/app/static/js/htmx-lite.js:231`

#### 4.2.2 End-to-end deliverable vs partial/demo
- **Conclusion: Pass**
- **Rationale:** full application structure remains complete and production-shaped.
- **Evidence:** `repo/backend/app/factory.py:24`, `repo/backend/app/routes/__init__.py:1`, `repo/docker-compose.yml:1`

### 4.3 Engineering and Architecture Quality

#### 4.3.1 Module decomposition and structure
- **Conclusion: Pass**
- **Rationale:** layered architecture unchanged and coherent.
- **Evidence:** `docs/design.md:5`, `repo/backend/app/factory.py:14`

#### 4.3.2 Maintainability/extensibility
- **Conclusion: Pass**
- **Rationale:** callback integrity check added cleanly in service layer with corresponding tests.
- **Evidence:** `backend/app/services/payment_service.py:72`, `backend/API_tests/test_payment_api.py:258`, `backend/unit_tests/test_payment_service.py:228`

### 4.4 Engineering Details and Professionalism

#### 4.4.1 Error handling, logging, validation, API design
- **Conclusion: Pass**
- **Rationale:** callback mismatch now returns deterministic validation error; existing error contract/logging remains intact.
- **Evidence:** `backend/app/services/payment_service.py:229`, `backend/app/factory.py:120`, `backend/app/services/errors.py:56`

#### 4.4.2 Product/service-level organization
- **Conclusion: Pass**
- **Rationale:** no regressions in service composition or delivery shape.
- **Evidence:** `repo/backend/app/templates/base.html:17`, `repo/backend/app/templates/finance/workspace.html:3`

### 4.5 Prompt Understanding and Requirement Fit

#### 4.5.1 Business goal and implicit constraint fit
- **Conclusion: Partial Pass**
- **Rationale:** major prior security gap fixed; remaining fit gap is the required-option pre-check UX not fully connected in executable enhancement logic.
- **Evidence:** `backend/app/templates/partials/dish_detail.html:12`, `backend/app/static/js/htmx-lite.js:167`, `docs/api-spec.md:118`

### 4.6 Aesthetics (frontend-only/full-stack)

#### 4.6.1 Visual and interaction quality
- **Conclusion: Partial Pass**
- **Rationale:** visual consistency is intact, but newly introduced required-option interaction likely does not fire in current JS enhancement implementation.
- **Evidence:** `backend/app/templates/partials/dish_detail.html:12`, `backend/app/static/js/htmx-lite.js:165`
- **Manual verification note:** browser click/change behavior should be manually verified for option pre-check panel updates.

## 5. Issues / Suggestions (Severity-Rated)

### Medium
1) **Severity: Medium**
   - **Title:** Required-option pre-check UI wiring is incomplete in enhancement runtime
   - **Conclusion:** Partial Fail
   - **Evidence:** `backend/app/templates/partials/dish_detail.html:12`, `backend/app/static/js/htmx-lite.js:167`, `backend/app/static/js/htmx-lite.js:231`
   - **Impact:** required-option validation endpoint exists, but the added fieldset `hx-post` behavior is not handled by current JS (which only binds form and hx-get patterns), so users may not receive immediate required-option prompts as intended.
   - **Minimum actionable fix:** either (a) add generic handler support for non-form `[hx-post]` elements in `htmx-lite.js`, or (b) move pre-check to a dedicated form/hx-get flow already supported by the script and add regression tests.

2) **Severity: Medium**
   - **Title:** README test script instructions do not match actual script location/flags
   - **Conclusion:** Partial Fail
   - **Evidence:** `README.md:85`, `README.md:90`, `README.md:98`, `repo/run_tests.sh:1`, `repo/run_tests.sh:7`
   - **Impact:** docs claim project-root one-click script and `--local` mode, but only `repo/run_tests.sh` exists and it always delegates to Docker compose; reviewers may fail setup.
   - **Minimum actionable fix:** align README with actual script behavior or implement documented `--local/--docker` options and add script at claimed location.

## 6. Security Review Summary

- **authentication entry points:** Pass (`backend/app/controllers/auth_controller.py:51`, `backend/app/services/auth_service.py:49`)
- **route-level authorization:** Pass (`backend/app/services/payment_service.py:52`, `backend/app/services/refund_service.py:39`, `backend/app/services/moderation_service.py:44`)
- **object-level authorization:** Pass for user-order and user-block scope (`backend/app/services/order_service.py:185`, `backend/app/repositories/community_repository.py:90`)
- **function-level authorization:** Pass (nonce-protected sensitive flows + callback binding fix) (`backend/app/services/refund_service.py:40`, `backend/app/services/moderation_service.py:117`, `backend/app/services/payment_service.py:225`)
- **tenant/user isolation:** Partial Pass (single-tenant app; user-level isolation present for core user-owned resources) (`backend/app/repositories/order_repository.py:123`)
- **admin/internal/debug protection:** Pass (`backend/app/controllers/ops_controller.py:17`, `backend/app/controllers/moderation_controller.py:96`)

## 7. Tests and Logging Review

- **Unit tests:** Pass for updated callback fix coverage (`backend/unit_tests/test_payment_service.py:228`)
- **API/integration tests:** Pass for updated callback fix coverage (`backend/API_tests/test_payment_api.py:258`)
- **Logging categories/observability:** Pass (`backend/app/logging.py:9`, `backend/app/factory.py:105`)
- **Sensitive-data leakage risk:** Pass (no regression observed; sanitization remains) (`backend/app/services/errors.py:56`, `backend/unit_tests/test_error_sanitization.py:37`)

## 8. Test Coverage Assessment (Static Audit)

### 8.1 Test Overview
- Pytest-based unit/API/frontend suites remain present; payment mismatch tests were added in both API and unit layers.
- Evidence: `backend/unit_tests/test_payment_service.py:228`, `backend/API_tests/test_payment_api.py:258`, `backend/pyproject.toml:12`.

### 8.2 Coverage Mapping Table

| Requirement / Risk Point | Mapped Test Case(s) | Key Assertion / Fixture / Mock | Coverage Assessment | Gap | Minimum Test Addition |
|---|---|---|---|---|---|
| Callback reference-binding integrity | `backend/API_tests/test_payment_api.py:258`, `backend/unit_tests/test_payment_service.py:228` | expects `400` + `reference_mismatch` | sufficient | none observed for this specific defect | n/a |
| Required-option immediate pre-check UX | No direct frontend/API test of new fieldset-trigger behavior | N/A | insufficient | runtime binding for non-form `hx-post` not tested | add frontend test that option change updates `#selection-status-*` via endpoint |
| Ops test hygiene cleanup | `backend/API_tests/test_ops_api.py:1` | trailing import removed | sufficient | none | n/a |
| Docs-to-code setup consistency | README/design updated | static text alignment partly improved | basically covered | README script behavior mismatch remains | add doc-check lint or CI assertion script |

### 8.3 Security Coverage Audit
- **authentication:** meaningfully covered.
- **route authorization:** meaningfully covered.
- **object-level authorization:** meaningfully covered for user-owned flows.
- **tenant/data isolation:** acceptable for single-tenant scope.
- **admin/internal protection:** meaningfully covered.
- **critical previous security defect:** callback reference-mismatch now explicitly tested and guarded.

### 8.4 Final Coverage Judgment
- **Partial Pass**
- Callback integrity coverage improved to sufficient; remaining meaningful gap is frontend required-option pre-check interaction coverage/verification.

## 9. Final Notes
- Re-test confirms the previously reported High-severity callback integrity issue is fixed.
- Remaining material concerns are now medium-severity and primarily UX wiring/documentation consistency.
