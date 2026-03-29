from __future__ import annotations

import sys
from pathlib import Path

from flask_migrate import upgrade

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.factory import create_app
from app.services.seed_service import seed_all


app = create_app()

with app.app_context():
    upgrade(directory="migrations")
    seed_all()
    print("Database migrated and seeded.")
