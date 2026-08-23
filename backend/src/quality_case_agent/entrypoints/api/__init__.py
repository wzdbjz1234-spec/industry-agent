"""HTTP entrypoint and dependency composition."""

from .app import app, build_demo_container, create_app

__all__ = ["app", "build_demo_container", "create_app"]
