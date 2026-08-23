"""Standalone mock QMS FastAPI entrypoint."""

from .app import app, create_mock_qms_app

__all__ = ["app", "create_mock_qms_app"]
