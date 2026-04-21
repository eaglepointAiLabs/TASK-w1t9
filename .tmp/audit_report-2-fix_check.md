# TablePay Fix Verification Report

## 1. Verdict
- Overall conclusion: Statistically Fixed, with limited live-verification caveats.

## 2. Scope and Boundary
- Reviewed: the six issue areas from the consolidated audit, the new regression tests, and the touched controllers/services/repository code.
- Not executed: app start, tests, Docker, browser flows, or concurrent workers.
- Caveat: concurrency-related fixes are verified statically, not under live multi-worker load.

## 3. Issue-by-Issue Verification

### 1) Malformed JSON container shapes can 500 core mutation endpoints
- Status: Fixed
- Evidence: `backend/app/controllers/payload_helpers.py:11`, `backend/app/controllers/order_controller.py:88`, `backend/app/controllers/catalog_controller.py:167`, `backend/app/controllers/community_controller.py:80`, `backend/app/controllers/payment_controller.py:81`, `backend/app/controllers/reconciliation_controller.py:169`, `backend/API_tests/test_payload_shape_api.py:30`
- Why this looks fixed: the affected mutation controllers now gate JSON bodies through `require_dict_payload()` and nested shape checks before service code runs. The new API tests explicitly cover JSON arrays, scalars, and wrong-shaped nested fields.

### 2) Async job claiming is not atomic
- Status: Fixed
- Evidence: `backend/app/repositories/ops_repository.py:32`, `backend/app/services/ops_service.py:76`, `backend/unit_tests/test_ops_service.py:235`
- Why this looks fixed: job claiming now uses a single SQL `UPDATE ... RETURNING` pattern through `claim_next_available_job()`, and `process_next_job()` consumes that atomic claim path instead of a read-then-update flow.

### 3) Restore verification is too shallow
- Status: Fixed
- Evidence: `backend/app/services/ops_service.py:390`, `backend/app/services/ops_service.py:396`, `backend/app/services/ops_service.py:415`, `backend/unit_tests/test_ops_service.py:143`
- Why this looks fixed: restore verification now checks the full bounded-context table set, not just `users` and `dishes`, and it validates representative row counts for reference tables.

### 4) Anonymous rate limiting can be bypassed by rotating the client cookie
- Status: Fixed
- Evidence: `backend/app/factory.py:25`, `backend/app/factory.py:105`, `backend/API_tests/test_rate_limit_identity_api.py:34`
- Why this looks fixed: anonymous rate-limit identity now comes from a server-observed fingerprint (`remote_addr` + `User-Agent`) rather than the `client_id` cookie alone. The new tests assert that cookie rotation does not create a fresh bucket.

### 5) Reconciliation exception resolution accepts arbitrary `action_type` values
- Status: Fixed
- Evidence: `backend/app/services/reconciliation_service.py:193`, `backend/API_tests/test_reconciliation_api.py:155`
- Why this looks fixed: `resolve_exception()` now rejects unknown `action_type` values with HTTP 400, and the reconciliation tests still cover the valid `resolve` flow.

### 6) Public selection-check leaks unpublished dish existence
- Status: Fixed
- Evidence: `backend/app/services/catalog_service.py:204`, `backend/app/controllers/catalog_controller.py:272`, `backend/API_tests/test_catalog_api.py:111`
- Why this looks fixed: the selection-check validator now applies the same visibility rule as public dish fetches, while still allowing managers to preview unpublished dishes. The API tests cover both public 404 behavior and manager preview behavior.

## 4. Residual Notes
- The original six issues all appear addressed in code and tests.
- The only remaining caution is live behavior: the atomic job claim and rate-limit identity fixes are strong statically, but they were not exercised in a running multi-worker environment here.
