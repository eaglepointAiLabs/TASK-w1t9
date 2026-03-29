from __future__ import annotations

import pytest

from app.extensions import db
from app.factory import create_app
from app.services.seed_service import seed_all


@pytest.fixture()
def app():
    app = create_app("test")
    with app.app_context():
        db.create_all()
        seed_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
