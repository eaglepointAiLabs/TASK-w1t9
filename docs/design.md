# TablePay Design

## Architecture

TablePay uses a single Flask service with a clean API boundary:

- `routes -> controllers -> services -> repositories -> models`
- Server-rendered Jinja templates for the HTML shell and role workspaces
- REST-style endpoints consumed by progressive enhancement requests
- SQLite as the local persistence layer
- UTC-normalized timestamps for persisted security, payment, refund, reconciliation, and ops events, with API serialization emitted as UTC `Z` timestamps

The frontend is not a SPA. Pages remain server-rendered and progressively enhanced through a local helper script, so there is no mandatory internet dependency.
The delivery keeps the source of truth in `fullstack/backend/app/templates` and `fullstack/backend/app/static`, while `fullstack/frontend` exists for frontend-facing docs and regression tests.

## Security

- Passwords are validated by a centralized complexity policy and stored with bcrypt hashes.
- Failed attempts are written to `auth_attempts`; the auth service enforces a 10-failure lockout inside a 15-minute rolling window.
- Sessions are stored in the `sessions` table and referenced by an HTTP-only cookie.
- CSRF tokens are stored in `csrf_tokens` and bound to a `client_id` cookie.
- Production startup rejects weak or missing signing/encryption secrets and requires secure cookies unless an explicit local-review HTTP override is enabled.
- `nonces` provide single-use 5-minute anti-replay protection for refunds and role changes.
- RBAC is modeled via `roles` and `user_roles`.
- Gateway signing keys and local backups are encrypted at rest with a Fernet key derived from local configuration.
- Structured logs include request id, actor, endpoint, error class, severity, and context.

## Catalog and ordering

- `dishes` hold publication state, sold-out state, sort order, archive timestamps, and base pricing.
- `dish_categories`, `dish_tags`, and `dish_tag_map` support menu filtering.
- `dish_availability_windows` allow time-boxed dish visibility checks.
- `dish_options`, `dish_option_values`, and `dish_option_rules` enforce required single-select and bounded multi-select flows.
- `dish_images` store validated local image uploads under `fullstack/data/uploads`.
- Customer browsing uses the same query path for HTML partial updates and JSON responses with cache support on hot reads.
- `carts` and `cart_items` store mutable pre-order state for each authenticated user.
- `orders`, `order_items`, and `order_status_history` persist immutable checkout snapshots and audit-friendly status transitions.
- `inventory_reservations` records stock consumption per checkout key.
- Checkout uses `BEGIN IMMEDIATE` so SQLite serializes competing order writers and prevents negative inventory.

## Payments and reconciliation

- `payment_transactions` record offline captures against orders with `pending`, `success`, and `failed` states.
- `payment_callbacks` store imported callback evidence including payload hash, verification status, verification message, signing key id, and callback linkage to the payment transaction when available.
- `callback_dedup_keys` enforce a 24-hour deduplication window per transaction reference and persist the deterministic response returned for duplicates.
- `gateway_signing_keys` store HMAC pre-shared secrets encrypted at rest.
- `reconciliation_runs`, `reconciliation_rows`, `reconciliation_exceptions`, and `reconciliation_actions` provide immutable reconciliation import history and operator resolution auditability.

## Refund governance

- `refunds` store requested amount, route, device id, approval state, and hold reasons.
- `refund_events` capture status transitions and actor context.
- `refund_risk_events` record anomaly detections such as repeated device usage bursts.
- `manager_stepup_challenges` enforce time-bounded password re-entry before high-risk refunds can move from `pending_stepup` to `approved`.
- Refund creation requires a single-use nonce and enforces original-route-only, cumulative cap checks, and step-up for high-risk scenarios.

## Community and moderation

- `posts`, `comments`, `likes`, `favorites`, `reports`, `user_blocks`, and `cooldown_events` model community interactions and abuse controls.
- Toggle-like and toggle-favorite endpoints are idempotent at the row level through unique constraints.
- Comment creation applies rapid-action throttling and per-target cooldown windows.
- `moderation_queue` stores triage items sourced from reports.
- `moderation_reason_codes` define controlled decision taxonomy.
- `moderation_actions` capture each moderator outcome with reason code, notes, and timeline state transition.
- `role_change_events` audit replay-safe role grants and revocations.
- Role governance is limited to Finance Admin operators, blocks self-role changes, and prevents removing the last Finance Admin assignment.

## Reliability and operations

- `job_queue` and `job_runs` provide SQLite-backed job state with retry and dead-letter fallback.
- `backup_jobs` and `restore_runs` capture encrypted local backup and restore-test history.
- `rate_limit_buckets` track per-user per-minute request counts.
- `circuit_breaker_state` tracks breaker state per endpoint path.
- Menu reads use an application cache with a 60-second TTL and explicit invalidation on dish mutations.
- Request hardening includes structured request context binding, per-user rate limiting, circuit-breaker gating, and structured operational error logging.
- Restore validation decrypts the latest backup to a dedicated restore-test directory and persists the result in `restore_runs`.

## Initialization flow

Container startup executes:

1. SQLite migration upgrade
2. Seed insertion for baseline roles, users, and local sample data
3. Waitress WSGI server start

## Testing strategy

- `fullstack/backend/unit_tests`: service and policy tests across auth, catalog, ordering, payments, reconciliation, refunds, community, moderation, and ops
- `fullstack/backend/API_tests`: endpoint coverage across the same surfaces
- `fullstack/frontend/API_tests`: SSR route and HTMX feedback coverage for login redirects, role-bound page access, and descriptive frontend error/success states
- `fullstack/frontend/unit_tests`: frontend session-isolation and role-switch regression coverage without introducing a separate SPA test harness
