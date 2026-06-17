"""FastAPI routers — auth / users / points / admin."""

from __future__ import annotations

from points_v2.api.routers import admin, auth, points, users

__all__ = ["auth", "users", "points", "admin"]
