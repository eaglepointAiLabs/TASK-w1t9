#!/usr/bin/env bash
# ============================================================
# TablePay – Unified Test Runner
# ============================================================
# One-click execution of all unit tests and API integration
# tests.  Exits with 0 only when every suite passes.
#
# Usage:
#   ./run_tests.sh              # Full suite via Docker (default)
#   ./run_tests.sh --local      # Run locally with pytest
#   ./run_tests.sh -- -k auth   # Filter tests by keyword
# ============================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

MODE="${1:-docker}"

separator() {
  echo ""
  echo "============================================================"
  echo "  $1"
  echo "============================================================"
  echo ""
}

# ---- Docker mode (default) ----------------------------------
if [ "$MODE" = "--docker" ] || [ "$MODE" = "docker" ]; then
  separator "TablePay – Running Full Test Suite (Docker)"

  shift 2>/dev/null || true
  exec docker compose --profile tests run --rm --build tests \
    python -m pytest \
    backend/unit_tests \
    backend/API_tests \
    frontend/API_tests \
    frontend/unit_tests \
    -v --tb=short \
    "$@"
fi

# ---- Local mode (pytest directly) ---------------------------
if [ "$MODE" = "--local" ]; then
  separator "TablePay – Running Full Test Suite (Local)"

  export PYTHONPATH="${ROOT_DIR}/backend"
  export TABLEPAY_ENV=test
  export FLASK_ENV=test

  TOTAL_PASS=0
  TOTAL_FAIL=0

  run_suite() {
    local suite_name="$1"
    local suite_path="$2"

    separator "$suite_name"

    if python -m pytest "$suite_path" -v --tb=short 2>&1; then
      echo ""
      echo "  [PASS] $suite_name completed successfully."
      TOTAL_PASS=$((TOTAL_PASS + 1))
    else
      echo ""
      echo "  [FAIL] $suite_name had failures."
      TOTAL_FAIL=$((TOTAL_FAIL + 1))
    fi
  }

  run_suite "Backend Unit Tests"     "backend/unit_tests/"
  run_suite "Backend API Tests"      "backend/API_tests/"
  run_suite "Frontend API Tests"     "frontend/API_tests/"
  run_suite "Frontend Unit Tests"    "frontend/unit_tests/"

  separator "TEST SUMMARY"
  echo "  Suites passed : $TOTAL_PASS"
  echo "  Suites failed : $TOTAL_FAIL"
  echo ""

  if [ "$TOTAL_FAIL" -gt 0 ]; then
    echo "  RESULT: FAIL"
    exit 1
  else
    echo "  RESULT: ALL TESTS PASSED"
    exit 0
  fi
fi

echo "Usage: $0 [--docker|--local]"
exit 1
