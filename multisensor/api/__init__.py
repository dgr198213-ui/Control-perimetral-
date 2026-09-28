"""API HTTP de solo lectura del núcleo multisensor."""

from .app import app, create_app

__all__ = ["app", "create_app"]
