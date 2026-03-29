# TablePay

TablePay is a local-first restaurant ordering, payment, reconciliation, refund, community, moderation, and operations system built with Flask, SQLite, and server-rendered templates with progressive enhancement.

## Startup

Run all runtime commands from the `fullstack` directory.

1. `docker compose up --build`
2. Open `http://localhost:5000/login`
3. Sign in with one of the seeded users:
   - `customer` / `Customer#1234`
   - `manager` / `Manager#12345`
   - `finance` / `Finance#12345`
   - `moderator` / `Moderator#123`

Container startup runs migrations and seeds automatically. No manual database preparation is required.
The container serves the app through Waitress rather than Flask's development server.

Local Docker review runs in `TABLEPAY_ENV=production` with explicit secrets and an explicit `ALLOW_INSECURE_HTTP=true` override so cookie security is still fail-fast in real production but usable over `http://localhost` for offline reviewer validation.

## Test runner

From the `fullstack` directory, run:

- `./run_tests.sh`

If the pinned dependencies are already installed and you need an offline rerun, use:

- `TABLEPAY_SKIP_PIP_INSTALL=1 ./run_tests.sh`

The script creates `.pytest-venv` inside `fullstack`, installs backend dependencies, and runs:

- `fullstack/backend/unit_tests`
- `fullstack/backend/API_tests`
- `fullstack/frontend/API_tests`
- `fullstack/frontend/unit_tests`

## Feature coverage

- Auth: bcrypt passwords, password policy, failed-attempt lockout, session cookies, CSRF tokens, RBAC, and anti-replay nonces.
- Catalog: categories, tags, availability windows, sold-out handling, required option groups, manager publish/archive/edit controls, and validated image uploads.
- Ordering: carts, cart items, checkout idempotency, pricing breakdown persistence, inventory reservations, and SQLite-safe concurrency control.
- Payments: offline capture, signed callback import/verify, encrypted rotating keys, and 24-hour deduplication by transaction reference.
- Reconciliation: CSV import, row normalization, variance detection, exception queues, and operator resolution actions.
- Refunds: partial and multiple refunds, original-route enforcement, cumulative cap checks, risk events, and password step-up.
- Community: likes, favorites, comments, reports, user blocks, cooldowns, and throttling controls.
- Moderation and governance: moderator queue, reason-coded outcomes, item history, nonce-protected role changes, and audit events.
- Operations: job tables, menu cache, per-user rate limiting, circuit breakers, structured logs, encrypted local backups, restore testing, and retention pruning.
- Frontend delivery: integrated SSR templates/static assets with HTMX-style progressive enhancement, descriptive toast feedback, and dedicated frontend route regression tests.
- Frontend test depth: route tests plus frontend session-isolation/unit regression tests, all runnable through `./run_tests.sh`.

## Reviewer runbook

1. `docker compose up --build`
2. Visit `http://localhost:5000/login`
3. Exercise the role surfaces:
   - Customer: `/menu`, `/cart`, `/community`
   - Store Manager: `/manager/dishes`
   - Finance Admin: `/finance/payments`, `/finance/reconciliation`, `/finance/refunds`
   - Moderator: `/moderation`
   - Governance: `/admin/roles`
4. `./run_tests.sh`
