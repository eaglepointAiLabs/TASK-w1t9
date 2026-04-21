# TablePay

> **Project type:** Full-stack web application (Python/Flask backend with server-rendered frontend). Runs entirely under Docker Compose.

## Docker-Only Run and Test

Run all commands from this directory (`repo/`).

## Start the App

```bash
docker-compose up --build -d
docker-compose ps
```

> `docker compose` (v2 plugin syntax) is also supported and equivalent — use whichever is available on your system.

This starts:

- web (TablePay app on http://localhost:9100)

The default compose is a **local review / development setup** — it enables bootstrap seeding and runs over plain HTTP. It is deliberately not a production deployment: the `production` environment (`TABLEPAY_ENV=production`) refuses to start with committed secrets or `BOOTSTRAP_SEED_DATA=true`.

If you need to disable local demo seeding, set `BOOTSTRAP_SEED_DATA=false` before start.

## Verify the App Is Running

After `docker-compose up` reports the `web` container as healthy, run the following deterministic checks. Each step has an exact expected result — if any deviates, the startup did not succeed.

### 1. Health check (no authentication required)

```bash
curl -s http://localhost:9100/healthz
```

Expected response (HTTP 200, JSON):

```json
{"code":"ok","message":"Service healthy.","data":{"status":"ok","app":"TablePay"}}
```

### 2. Public menu API (verifies database seed)

```bash
curl -s -H "Accept: application/json" "http://localhost:9100/api/dishes?category=noodles"
```

Expected: HTTP 200 with JSON where `data[0].category_slug == "noodles"` and `data[0].name == "Signature Beef Noodles"`.

### 3. UI smoke test

Open http://localhost:9100/menu in a browser. You should see the seeded menu including **Signature Beef Noodles** under the **Noodles** category.

### 4. Authenticated login (verifies identity seed)

Go to http://localhost:9100/login and sign in with `manager` / `Manager#12345`. You should be redirected to the manager dashboard at `/manager/dishes` and see the seeded catalog.

If all four checks pass, the system is functioning as intended.

## Run Tests (Docker Only)

Run the full suite:

```bash
docker-compose --profile tests run --rm --build tests
```

Or use the wrapper:

```bash
./run_tests.sh
```

Run targeted suites:

```bash
docker-compose --profile tests run --rm --build tests python -m pytest backend/unit_tests -q
docker-compose --profile tests run --rm --build tests python -m pytest backend/API_tests -q
docker-compose --profile tests run --rm --build tests python -m pytest frontend/API_tests -q
docker-compose --profile tests run --rm --build tests python -m pytest frontend/unit_tests -q
docker-compose --profile e2e run --rm --build e2e
docker-compose --profile e2e rm -sf web-e2e
```

## Frontend E2E (Docker Only)

This suite runs fully in Docker using an isolated E2E app container plus an E2E test container.

```bash
docker-compose --profile e2e run --rm --build e2e
docker-compose --profile e2e rm -sf web-e2e
```

## Default Login Credentials

Available when bootstrap seeding is enabled (`BOOTSTRAP_SEED_DATA=true`). Each credential is bound to a specific application role — use the credential that matches the role you want to exercise.

| Username    | Password         | Role            | Purpose                                                     |
| ----------- | ---------------- | --------------- | ----------------------------------------------------------- |
| `customer`  | `Customer#1234`  | Customer        | Browse menu, place orders, submit reviews.                  |
| `manager`   | `Manager#12345`  | Store Manager   | Create/publish dishes, manage catalog, upload dish images.  |
| `admin`     | `Admin#123456`   | Finance Admin   | Full finance + operations access (superset of `finance`).   |
| `finance`   | `Finance#12345`  | Finance Admin   | Reconciliation, refunds, backups, ops job processing.       |
| `moderator` | `Moderator#123`  | Moderator       | Review and moderate community content and reports.          |

## Stop and Cleanup

```bash
docker-compose down -v --remove-orphans
```
