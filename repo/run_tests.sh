#!/usr/bin/env bash
# ============================================================
# TablePay – Unified Test Runner
# ============================================================
# One-click execution of all unit tests and API integration
# tests via Docker.  Exits with 0 only when every suite passes.
#
# Usage:
#   ./run_tests.sh              # Full suite
#   ./run_tests.sh -- -k auth   # Filter tests by keyword
# ============================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

echo ""
echo "============================================================"
echo "  TablePay – Running Full Test Suite"
echo "============================================================"
echo ""
echo "  Suites:"
echo "    - backend/unit_tests    (service and policy tests)"
echo "    - backend/API_tests     (endpoint integration tests)"
echo "    - frontend/API_tests    (SSR route and HTMX tests)"
echo "    - frontend/unit_tests   (template component tests)"
echo ""

exec docker compose --profile tests run --rm --build tests \
  python -m pytest \
  backend/unit_tests \
  backend/API_tests \
  frontend/API_tests \
  frontend/unit_tests \
  -v --tb=short \
  "$@"
