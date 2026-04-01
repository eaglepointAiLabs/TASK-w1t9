# Questions And Assumptions (Blocker-Level)

## 1) Frontend placement is ambiguous

The Gap: The prompt requires all source under fullstack and also mentions a fullstack/frontend directory, while allowing Flask templates/static as an alternative. This leaves ownership and structure unclear for implementation and review.

The Interpretation: We will treat frontend delivery as server-rendered templates/static assets in Flask, and keep fullstack/frontend as documentation/test placeholder unless a separate frontend runtime is explicitly required.

Proposed Implementation: Keep UI in backend template/static layers with a strict API boundary (HTML pages + REST endpoints). Document this architecture explicitly in fullstack/frontend/README.md and fullstack/README.md so reviewers can verify where frontend logic lives.

## 2) Role governance authority is not fully specified

The Gap: The prompt defines Customer, Store Manager, Finance Admin, and Moderator, but does not explicitly define which role is the final authority for role changes and whether self-role changes are allowed.

The Interpretation: We will treat role changes as privileged governance actions allowed only to Finance Admin operators, with explicit prohibition on self-role changes.

Proposed Implementation: Enforce Finance Admin-only role changes in a dedicated service guard, reject self-role mutations, preserve at least one Finance Admin assignment, and keep nonce plus audit-event logging on every mutation.

## 3) Payment lifecycle state machine is underdefined

The Gap: Payment capture, callback import, and reconciliation are required, but legal transitions between payment states are not fully defined (for example pending -> success -> failed, or callback conflict behavior).

The Interpretation: We will enforce a deterministic state machine where callbacks are validated first, and only legal transitions are accepted; conflicting transitions become auditable exceptions.

Proposed Implementation: Define an explicit payment_state_transition table or enum transition map in service layer. Reject illegal transitions with 409, preserve callback evidence, and emit reconciliation exception records when external callback state conflicts with local state.

## 4) Callback idempotency semantics are incomplete

The Gap: The prompt asks for 24-hour uniqueness per transaction reference, but does not specify behavior for same reference with different payload hashes/signatures inside the window.

The Interpretation: We will treat the first verified callback within the 24-hour window as authoritative and return a deterministic replay response for exact duplicates; mismatched payload replays are marked as suspicious duplicates.

Proposed Implementation: Persist (transaction_reference, payload_hash, first_callback_id, expires_at). If same reference arrives with different payload_hash before expiry, store security event + return conflict code while preserving original authoritative response contract.

## 5) Refund step-up approver identity is unclear

The Gap: Prompt text requires step-up for risky refunds but does not clearly specify whether the approver must be the same operator, a second operator, or a manager persona.

The Interpretation: We will use same-operator password re-entry as baseline step-up, with extension point for dual-approval if policy hardens later.

Proposed Implementation: Implement challenge records with status/expiry and operator binding now; abstract approver strategy behind a policy interface so the flow can later switch to dual-control without schema breakage.

## 6) Inventory boundary is ambiguous for options/add-ons

The Gap: Prompt requires inventory safety and rich option modeling, but does not specify whether inventory applies only at dish level or also at option-value level (for example limited add-ons).

The Interpretation: We will enforce dish-level inventory as mandatory baseline and treat option-level inventory as optional extension unless explicitly demanded.

Proposed Implementation: Keep dish stock as source of truth for checkout locking. Add nullable option_value_stock fields and reservation hooks behind feature flags so option-level stock can be enabled without rewriting checkout transaction logic.

## 7) Reconciliation tolerance policy is undefined

The Gap: Prompt requires variance and exception workflow, but does not define acceptable tolerance thresholds (for example rounding differences) or auto-resolve conditions.

The Interpretation: We will default to strict equality for amount/currency/status and route all mismatches to manual exception resolution.

Proposed Implementation: Implement a reconciliation policy object with defaults: amount_tolerance=0, exact currency match, exact status match. Keep policy configurable in local config for future domain calibration.

## 8) Community moderation SLAs and escalation are missing

The Gap: Prompt requires reports, queue, reason codes, and cooldown communication, but does not define moderation SLA, priority strategy, or escalation conditions.

The Interpretation: We will prioritize deterministic queue behavior: reason-based priority buckets plus FIFO within each bucket.

Proposed Implementation: Add queue fields for priority, created_at, and escalation_at. Implement scheduler-friendly query ordering and optional escalation job that marks overdue high-risk reports for moderator attention.

## 9) Backup key management and disaster recovery are incomplete

The Gap: Prompt requires encrypted nightly backups and offline restore, but does not define encryption key rotation/recovery procedure if key material is lost.

The Interpretation: We will require local key continuity as an operational prerequisite and document that backups are not recoverable without key material.

Proposed Implementation: Store key metadata (version, created_at, active flag) and backup-key version linkage; provide a local runbook for key rotation and a periodic restore test that validates both backup file and key availability.

## 10) Reliability controls scope is not fully bounded

The Gap: Prompt requires rate limiting and circuit breaker, but does not specify endpoint exemptions (for example login/logout/health) or per-role overrides.

The Interpretation: We will apply defaults globally with explicit allowlist exemptions for auth bootstrap and operational health paths to avoid self-inflicted lockouts.

Proposed Implementation: Add centralized policy config: endpoint_pattern, limiter profile, breaker profile, exemption flag. Evaluate policy in before_request middleware and keep decisions observable via structured logs and admin diagnostics endpoints.
