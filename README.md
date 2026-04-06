# TablePay Restaurant Ordering & Community

A full-featured restaurant ordering and community engagement platform with offline payment capture, reconciliation, secure refund handling, rich dish/option modeling, high-concurrency ordering, and community governance.

## Project Structure

```
TablePay-Restaurant-Ordering/
├── README.md                  # This file
├── docs/                      # All project documentation
│   ├── api-spec.md            # Complete REST API specification
│   ├── design.md              # Architecture and security design
│   ├── disaster-recovery-runbook.md
│   └── questions.md           # FAQ and design decisions
├── repo/                      # Application source code
│   ├── README.md              # Docker run and test commands
│   ├── docker-compose.yml
│   ├── Dockerfile.tests
│   ├── run_tests.sh
│   ├── backend/               # Flask backend application
│   │   ├── app/               # Main application package
│   │   │   ├── factory.py     # Flask app factory
│   │   │   ├── config.py      # Environment configuration
│   │   │   ├── controllers/   # Request handlers
│   │   │   ├── routes/        # Blueprint route registration
│   │   │   ├── services/      # Business logic layer
│   │   │   ├── repositories/  # Data access layer
│   │   │   ├── models/        # SQLAlchemy ORM models
│   │   │   ├── templates/     # Jinja2 server-rendered HTML
│   │   │   └── static/        # CSS and JS assets
│   │   ├── migrations/        # Alembic database migrations
│   │   ├── API_tests/         # API integration tests
│   │   ├── unit_tests/        # Unit tests
│   │   ├── conftest.py        # Pytest fixtures
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── frontend/              # Frontend SSR and E2E tests
│       ├── API_tests/
│       ├── unit_tests/
│       └── e2e/
└── sessions/                  # Runtime session data
```

## Quick Start

All commands are run from the `repo/` directory.

### Start the Application

```bash
cd repo
docker compose up --build -d
docker compose ps
```

The app starts on **http://localhost:9100**.

### Default Login Credentials

Available when bootstrap seeding is enabled (`BOOTSTRAP_SEED_DATA=true`, the default).

| Role           | Username    | Password          |
|----------------|-------------|-------------------|
| Customer       | customer    | Customer#1234     |
| Store Manager  | manager     | Manager#12345     |
| Finance Admin  | finance     | Finance#12345     |
| Admin          | admin       | Admin#123456      |
| Moderator      | moderator   | Moderator#123     |

### Configuration

Key environment variables (set before `docker compose up`):

| Variable                   | Default              | Description                                      |
|----------------------------|----------------------|--------------------------------------------------|
| `TABLEPAY_ENV`             | `production`         | Config profile (`development`, `testing`, `production`) |
| `BOOTSTRAP_SEED_DATA`      | `true`               | Seed demo users, dishes, and community posts     |
| `SECRET_KEY`               | (auto-generated)     | Flask session secret                             |
| `KEY_ENCRYPTION_SECRET`    | `tablepay-local-encryption-key` | Fernet key for signing-key encryption at rest |
| `SESSION_COOKIE_SECURE`    | `true` (production)  | Enforce HTTPS-only session cookies               |
| `NIGHTLY_BACKUP_HOUR_UTC`  | `3`                  | Hour (UTC) for automatic encrypted backup        |

## Running Tests

All test commands are run from the `repo/` directory.

### Full Test Suite

```bash
cd repo
docker compose --profile tests run --rm --build tests
```

Or use the wrapper script:

```bash
cd repo
./run_tests.sh
```

### Targeted Test Suites

```bash
cd repo

# Backend unit tests
docker compose --profile tests run --rm --build tests python -m pytest backend/unit_tests -q

# Backend API integration tests
docker compose --profile tests run --rm --build tests python -m pytest backend/API_tests -q

# Frontend SSR route tests
docker compose --profile tests run --rm --build tests python -m pytest frontend/API_tests -q

# Frontend unit tests
docker compose --profile tests run --rm --build tests python -m pytest frontend/unit_tests -q

# End-to-end browser tests
docker compose --profile e2e run --rm --build e2e
docker compose --profile e2e rm -sf web-e2e
```

## Architecture Overview

- **Backend**: Flask with SQLAlchemy ORM, SQLite persistence, bcrypt password hashing
- **Frontend**: Server-side rendered Jinja2 templates with HTMX progressive enhancement
- **Auth**: Local username/password, cookie-based sessions, CSRF protection, account lockout (10 attempts / 15 min), 12-char minimum passwords
- **Payments**: Offline capture, WeChat Pay JSAPI simulator, signed callback verification with rotating encrypted keys, 24-hour idempotency dedup
- **Refunds**: Partial/multiple refunds, original-route enforcement, step-up manager confirmation for >$50 or anomaly detection (3+ refunds from same device in 30 min)
- **Reconciliation**: CSV statement import, variance detection (amount/status mismatch, missing/duplicate references), operator resolution workflow
- **Community**: Like, favorite, comment, report, block; throttle (5 actions/min), cooldown (30s between comments), block-aware interaction rules
- **Moderation**: Flagged-item queue with reason codes and outcomes (dismiss/warn/hide/remove/suspend)
- **Operations**: Async job queue (SQLite-backed), rate limiting (60 req/min/user), circuit breaking, structured logging, nightly encrypted backups (14-day retention), tested restore procedure
- **Anti-replay**: Per-request nonces with 5-minute expiration for refunds and role changes

## Documentation

- [API Specification](docs/api-spec.md) - Complete REST endpoint reference with request/response formats
- [Architecture & Design](docs/design.md) - System design, security model, data model, testing strategy
- [Disaster Recovery Runbook](docs/disaster-recovery-runbook.md) - Backup/restore procedures and validation checklist
- [Design Questions & Decisions](docs/questions.md) - FAQ and architectural decision records

## Stop and Cleanup

```bash
cd repo
docker compose down -v --remove-orphans
```
