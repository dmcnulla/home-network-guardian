from __future__ import annotations

import logging

import typer

from home_network_guardian.config import Settings
from home_network_guardian.engine import GuardianEngine

app = typer.Typer(help="Home Network Guardian")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


@app.command()
def scan_once() -> None:
    """Run one full monitoring cycle."""
    setup_logging()
    settings = Settings()
    GuardianEngine(settings).run_once()
    typer.echo("Scan complete")


@app.command()
def daemon() -> None:
    """Run monitoring forever."""
    setup_logging()
    settings = Settings()
    GuardianEngine(settings).run_forever()


@app.command()
def init_baseline() -> None:
    """Initialize baseline MAC inventory by running one scan."""
    setup_logging()
    settings = Settings()
    GuardianEngine(settings).run_once()
    typer.echo("Baseline initialized")


if __name__ == "__main__":
    app()
