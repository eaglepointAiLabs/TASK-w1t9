from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from app.config import TestConfig
from app.extensions import db
from app.factory import create_app
from app.services.seed_service import (
    seed_all,
    seed_catalog_data,
    seed_community_data,
    seed_identity_data,
    seed_moderation_data,
    seed_payment_keys,
)


def _build_app(database_uri: str | None = None):
    if database_uri is not None:
        original_uri = TestConfig.SQLALCHEMY_DATABASE_URI
        TestConfig.SQLALCHEMY_DATABASE_URI = database_uri
    else:
        original_uri = None
    app = create_app("test")
    if original_uri is not None:
        TestConfig.SQLALCHEMY_DATABASE_URI = original_uri
    return app


@pytest.fixture()
def app():
    app = _build_app()
    with app.app_context():
        db.create_all()
        seed_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def tmp_path():
    temp_root = Path(__file__).resolve().parents[1] / "data" / "test-temp"
    temp_root.mkdir(parents=True, exist_ok=True)
    path = temp_root / f"tablepay-tests-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture()
def file_app(tmp_path: Path):
    database_path = tmp_path / "tablepay-test.db"
    app = _build_app(f"sqlite:///{database_path.as_posix()}")
    with app.app_context():
        db.create_all()
        seed_identity_data()
        seed_catalog_data()
        seed_payment_keys()
        seed_community_data()
        seed_moderation_data()
        yield app
        db.session.remove()
        db.drop_all()
