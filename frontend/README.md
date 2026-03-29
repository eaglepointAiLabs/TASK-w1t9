TablePay uses integrated Flask SSR rather than a separate SPA build.

Frontend source of truth from this repo root:

- HTML templates: `backend/app/templates`
- Styles and progressive-enhancement JS: `backend/app/static`
- Frontend route tests: `frontend/API_tests`
- Frontend session/unit tests: `frontend/unit_tests`

Project-wide verification:

- `./run_tests.sh`

Standalone frontend route verification from the repo root:

- `PYTHONPATH=backend python -m pytest frontend/API_tests -q`

Standalone frontend session/unit verification from the repo root:

- `PYTHONPATH=backend python -m pytest frontend/unit_tests -q`

PowerShell equivalents:

- `$env:PYTHONPATH='backend'; python -m pytest frontend/API_tests -q`
- `$env:PYTHONPATH='backend'; python -m pytest frontend/unit_tests -q`
