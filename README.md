# TablePay

TablePay is a local-first restaurant ordering, payment, reconciliation, refund, community, moderation, and operations system built with Flask, SQLite, and server-rendered templates with progressive enhancement.

Run every documented command from this repository root.

## Startup

Primary review path:

1. `docker compose up --build -d`
2. `docker compose ps`
3. Wait for the `web` service to report `healthy`
4. Open `http://localhost:5000/login`

Seeded users:

- `customer` / `Customer#1234`
- `manager` / `Manager#12345`
- `finance` / `Finance#12345`
- `moderator` / `Moderator#123`

Container startup runs migrations and seeds automatically. The container serves the app through Waitress rather than Flask's development server.

Deterministic container health is exposed through `/healthz` and Docker's built-in `healthcheck`, so reviewers can verify boot state non-interactively with `docker compose ps`.

## Test Runner

Project-wide verification:

- `./run_tests.sh`

Offline rerun when dependencies are already installed:

- `TABLEPAY_SKIP_PIP_INSTALL=1 ./run_tests.sh`

The script creates `.pytest-venv` in the repo root, runs a documentation smoke check, then executes:

- `python -m pytest backend/unit_tests -q`
- `python -m pytest backend/API_tests -q`
- `python -m pytest frontend/API_tests -q`
- `python -m pytest frontend/unit_tests -q`

## Feature Coverage

- Auth: bcrypt passwords, password policy, failed-attempt lockout, session cookies, CSRF tokens, RBAC, and anti-replay nonces.
- Catalog: categories, tags, availability windows, sold-out handling, required option groups, manager publish/archive/edit controls, validated image uploads, and a structured dish editor for windows, rules, and price deltas.
- Catalog async ops: queue-backed bulk menu update jobs for publish/archive changes.
- Ordering: carts, cart items, checkout idempotency, pricing breakdown persistence, inventory reservations, and SQLite-safe concurrency control.
- Payments: offline capture, callback verification preview, signed callback import/verify, encrypted rotating keys, and 24-hour deduplication by transaction reference.
- Payments simulator: JSAPI callback simulation endpoint and workspace controls that sign and import callbacks through the same verification pipeline.
- Reconciliation: CSV import, row normalization, variance detection, exception queues, and operator resolution actions.
- Reconciliation async ops: optional queued import processing backed by the ops job worker.
- Refunds: partial and multiple refunds, original-route enforcement, cumulative cap checks, risk events, manager-gated high-risk approval, and password step-up for Store Manager approval.
- Community: likes, favorites, comments, reports, user blocks, cooldowns, and throttling controls.
- Moderation and governance: moderator queue, reason-coded outcomes, item history, nonce-protected role changes, and audit events.
- Operations: job tables, menu cache, per-user rate limiting, circuit breakers, structured logs, encrypted local backups, restore testing, retention pruning, and deterministic container health checks.
- Frontend delivery: integrated SSR templates/static assets with HTMX-style progressive enhancement, descriptive toast feedback, and dedicated route/session regression coverage.

## Reviewer Runbook

1. `docker compose up --build -d`
2. `docker compose ps`
3. Visit `http://localhost:5000/login`
4. Exercise the role surfaces:
   - Customer: `/menu`, `/cart`, `/community`
   - Store Manager: `/manager/dishes`, `/finance/refunds`
   - Finance Admin: `/finance/payments`, `/finance/reconciliation`, `/finance/refunds`
   - Moderator: `/moderation`
   - Governance: `/admin/roles`
5. `./run_tests.sh`
