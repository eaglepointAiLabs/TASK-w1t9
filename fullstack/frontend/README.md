TablePay uses integrated Flask SSR rather than a separate SPA build.

Frontend source of truth:
- HTML templates: `fullstack/backend/app/templates`
- Styles and progressive-enhancement JS: `fullstack/backend/app/static`
- Frontend route and HTMX regression tests: `fullstack/frontend/API_tests`

This `fullstack/frontend` directory exists to make frontend ownership explicit for review, docs, and frontend-facing test coverage. It does not contain a separate runtime bundle.

Standalone frontend route verification from the `fullstack` directory:
- `PYTHONPATH=backend python -m pytest frontend/API_tests -q`

Standalone frontend session/unit verification from the `fullstack` directory:
- `PYTHONPATH=backend python -m pytest frontend/unit_tests -q`

Project-wide verification:
- `./run_tests.sh`
