from __future__ import annotations

import click
from flask import Flask

from app.services.seed_service import seed_identity_data


def register_cli(app: Flask) -> None:
    @app.cli.command("seed")
    def seed() -> None:
        seed_identity_data()
        click.echo("Seeded identity data.")
