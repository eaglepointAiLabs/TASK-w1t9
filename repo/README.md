# TablePay

## Docker-Only Run and Test

Run all commands from the repository root.

## Start the App

```bash
docker compose up --build -d
docker compose ps
```

This starts:

- web (TablePay app on http://localhost:9100)

By default in this production-labeled compose setup:

- secure cookies are enforced
- insecure HTTP override is disabled
- bootstrap data seeding is enabled

If you need to disable local demo seeding, set `BOOTSTRAP_SEED_DATA=false` before start.

## Run Tests (Docker Only)

Run the full suite:

```bash
docker compose --profile tests run --rm --build tests
```

Or use the wrapper:

```bash
./run_tests.sh
```

Run targeted suites:

```bash
docker compose --profile tests run --rm --build tests python -m pytest backend/unit_tests -q
docker compose --profile tests run --rm --build tests python -m pytest backend/API_tests -q
docker compose --profile tests run --rm --build tests python -m pytest frontend/API_tests -q
docker compose --profile tests run --rm --build tests python -m pytest frontend/unit_tests -q
docker compose --profile e2e run --rm --build e2e
docker compose --profile e2e rm -sf web-e2e
```

## Frontend E2E (Docker Only)

This suite runs fully in Docker using an isolated E2E app container plus an E2E test container.

```bash
docker compose --profile e2e run --rm --build e2e
docker compose --profile e2e rm -sf web-e2e
```

## Default Login Credentials

Available when bootstrap seeding is enabled (`BOOTSTRAP_SEED_DATA=true`).

- customer / Customer#1234
- manager / Manager#12345
- admin / Admin#123456
- finance / Finance#12345
- moderator / Moderator#123

## Disaster Recovery Runbook

See [../docs/disaster-recovery-runbook.md](../docs/disaster-recovery-runbook.md) for a full offline backup and restore drill procedure, validation checklist, and evidence template.

## Stop and Cleanup

```bash
docker compose down -v --remove-orphans
```
