#!/usr/bin/env bash
# ============================================================
# TablePay – Unified Test Runner
# ============================================================
# Runs ALL test suites inside Docker with zero host-side
# dependencies.  No .env file, no manual seeding, no
# migration step.  Everything is bootstrapped inside the
# containers automatically.
#
# Phases
# ------
#   1. Unit + API + frontend  (Flask test client, in-memory DB)
#      Seeds all reference data internally; needs no live server.
#
#   2. E2E journeys            (real HTTP against a live server)
#      Builds and starts web-e2e, waits for its health check,
#      runs the e2e suite, then removes web-e2e regardless of
#      outcome.
#
# Usage
# -----
#   ./run_tests.sh               # All suites
#   ./run_tests.sh -- -k auth    # Filter Phase 1 by pytest keyword
# ============================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# ---------------------------------------------------------------
# Resolve Docker Compose (v2 plugin or v1 standalone)
# ---------------------------------------------------------------
if docker compose version > /dev/null 2>&1; then
    DC="docker compose"
elif docker-compose version > /dev/null 2>&1; then
    DC="docker-compose"
else
    echo ""
    echo "ERROR: Docker Compose not found." >&2
    echo "       Install Docker Desktop or the standalone docker-compose package." >&2
    echo ""
    exit 1
fi

# ---------------------------------------------------------------
# Pre-flight: Docker daemon must be reachable
# ---------------------------------------------------------------
if ! docker info > /dev/null 2>&1; then
    echo ""
    echo "ERROR: Docker daemon is not running." >&2
    echo "       Start Docker Desktop (or the Docker service) and retry." >&2
    echo ""
    exit 1
fi

echo ""
echo "============================================================"
echo "  TablePay – Full Test Suite"
echo "============================================================"
echo "  Compose : $DC"
echo ""
echo "  Phase 1  unit + API + frontend  (Flask test client)"
echo "  Phase 2  E2E journeys           (real HTTP, live server)"
echo ""

# ---------------------------------------------------------------
# Phase 1 – unit, API, frontend
#
# Runs entirely inside the 'tests' container:
#   • in-memory SQLite database created fresh per test
#   • all seed data (users, catalog, payments …) applied by
#     conftest.py fixtures — no external state required
#   • no live server, no env vars needed on the host
# ---------------------------------------------------------------
echo "------------------------------------------------------------"
echo "[1/2] Building test image → unit / API / frontend tests"
echo "------------------------------------------------------------"
echo ""

$DC --profile tests run --rm --build tests \
    python -m pytest \
    backend/unit_tests \
    backend/API_tests \
    frontend/API_tests \
    frontend/unit_tests \
    -v --tb=short \
    "$@"

echo ""
echo "[1/2] All unit / API / frontend tests passed."
echo ""

# ---------------------------------------------------------------
# Phase 2 – E2E journeys
#
# docker compose starts web-e2e (TABLEPAY_ENV=development,
# BOOTSTRAP_SEED_DATA=true), waits for /healthz to return
# {"code":"ok"}, then runs the e2e container which fires real
# HTTP requests via urllib.  The live server is removed at the
# end regardless of test outcome.
# ---------------------------------------------------------------
echo "------------------------------------------------------------"
echo "[2/2] Starting live server (web-e2e) → E2E journeys"
echo "------------------------------------------------------------"
echo ""

# Remove any web-e2e left over from a previous interrupted run
$DC --profile e2e rm -sf web-e2e 2>/dev/null || true

e2e_exit=0
$DC --profile e2e run --rm --build e2e \
    python -m pytest \
    frontend/e2e \
    -v --tb=short \
    || e2e_exit=$?

# Always remove the live server, even when tests fail
$DC --profile e2e rm -sf web-e2e 2>/dev/null || true

if [ "$e2e_exit" -ne 0 ]; then
    echo ""
    echo "[2/2] E2E tests FAILED (exit $e2e_exit)." >&2
    echo ""
    exit "$e2e_exit"
fi

echo ""
echo "[2/2] All E2E tests passed."
echo ""

echo "============================================================"
echo "  All suites passed."
echo "============================================================"
echo ""
