# TablePay Follow-up Recheck Round 3

Static recheck of the issue set from the first audit report and the first two follow-up reports, using the current codebase state only.

## Verdict
- Overall conclusion: Pass
- Summary: All five previously reported issue areas now have static evidence of fixes in the current implementation.

## Rechecked Issues

### 1) Disabled gateway signing keys are still accepted
- Status: Resolved
- Conclusion: Fixed
- Evidence:
  - `backend/app/services/payment_service.py:188-197`
  - `backend/app/services/payment_service.py:240-246`
  - `backend/API_tests/test_payment_api.py:484-558`
- Rationale: Both callback verification paths now reject inactive signing keys via `key.is_active`, and the API tests explicitly revoke `simulator-v1` and assert rejection in import and preview flows.
- Impact: The revoked-key acceptance gap from the first report is no longer present in the current code.

### 2) Reconciliation ignores currency mismatches
- Status: Resolved
- Conclusion: Fixed
- Evidence:
  - `backend/app/services/reconciliation_service.py:85-100`
  - `backend/API_tests/test_reconciliation_api.py:171-245`
- Rationale: Reconciliation now compares payment currency against the CSV row currency and classifies differences as `currency_mismatch`. The regression tests cover both mismatch and matching cases.
- Impact: Currency drift is now surfaced as an exception instead of being silently matched.

### 3) Blocked users can still like/favorite/report the blocked author
- Status: Resolved
- Conclusion: Fixed
- Evidence:
  - `backend/app/services/community_service.py:23-44`
  - `backend/app/services/community_service.py:70-99`
  - `backend/unit_tests/test_community_service.py:167-212`
- Rationale: `_enforce_block_rules()` is now called from like, favorite, comment, and report flows. The unit tests explicitly assert that blocked users cannot like, favorite, report, or comment on blocked authors’ posts.
- Impact: The block rule now applies consistently across the previously uncovered community actions.

### 4) Report creation is not atomic with moderation queue insertion
- Status: Resolved
- Conclusion: Fixed
- Evidence:
  - `backend/app/services/community_service.py:80-99`
  - `backend/app/services/moderation_service.py:26-42`
  - `backend/app/repositories/community_repository.py:84-88`
  - `backend/app/repositories/moderation_repository.py:38-42`
  - `backend/unit_tests/test_moderation_service.py:12-41`
- Rationale: `create_report()` now wraps report creation, queue-item insertion, commit, and rollback in one transaction boundary. The repository methods only flush, and the new atomicity test patches queue insertion to fail and verifies the report count does not increase.
- Impact: Moderation intake is no longer left in a half-persisted state when queue item creation fails.

### 5) Payment capture accepts arbitrary status values
- Status: Resolved
- Conclusion: Fixed
- Evidence:
  - `backend/app/services/payment_service.py:71-77`
  - `backend/API_tests/test_payment_api.py:561-604`
- Rationale: `capture_payment()` now validates status against the allowed set `pending`, `success`, and `failed`. The API tests confirm invalid values are rejected and valid values are accepted.
- Impact: Unbounded payment status values are no longer persisted.

## Notes
- I did not run the application, tests, Docker, or external services.
- This report is intentionally limited to the issue set already identified in the earlier reports and does not broaden the scope.
