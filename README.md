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
```

## Default Login Credentials

- customer / Customer#1234
- manager / Manager#12345
- finance / Finance#12345
- moderator / Moderator#123

## Stop and Cleanup

```bash
docker compose down -v --remove-orphans
```
