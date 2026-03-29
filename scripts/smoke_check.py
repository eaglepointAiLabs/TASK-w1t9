from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
FRONTEND_README = ROOT / "frontend" / "README.md"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    _require((ROOT / "backend").is_dir(), "Missing backend directory at repo root.")
    _require((ROOT / "frontend").is_dir(), "Missing frontend directory at repo root.")
    _require((ROOT / "run_tests.sh").is_file(), "Missing run_tests.sh at repo root.")
    _require((ROOT / "docker-compose.yml").is_file(), "Missing docker-compose.yml at repo root.")
    _require((ROOT / "backend" / "requirements.txt").is_file(), "Missing backend requirements file.")
    _require((ROOT / "backend" / "scripts" / "healthcheck.py").is_file(), "Missing Docker healthcheck script.")

    readme_text = README.read_text(encoding="utf-8")
    frontend_text = FRONTEND_README.read_text(encoding="utf-8")

    _require("fullstack/" not in readme_text, "README.md still references the old fullstack/ root.")
    _require("fullstack/" not in frontend_text, "frontend/README.md still references the old fullstack/ root.")

    required_readme_commands = [
        "docker compose up --build -d",
        "docker compose ps",
        "./run_tests.sh",
        "python -m pytest backend/unit_tests -q",
    ]
    for command in required_readme_commands:
        _require(command in readme_text, f"README.md is missing documented command: {command}")

    required_frontend_commands = [
        "PYTHONPATH=backend python -m pytest frontend/API_tests -q",
        "PYTHONPATH=backend python -m pytest frontend/unit_tests -q",
    ]
    for command in required_frontend_commands:
        _require(command in frontend_text, f"frontend/README.md is missing documented command: {command}")

    print("Documentation smoke check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
