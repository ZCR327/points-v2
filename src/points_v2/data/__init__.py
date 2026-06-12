"""Data access layer — JSON-backed Repository 集合。

依赖方向：``core`` + ``domain`` ← ``data``（data 不依赖 service / api / ui）。
"""

from __future__ import annotations

from points_v2.data.audit_repo import AuditRepository
from points_v2.data.base import JsonRepository
from points_v2.data.notification_repo import NotificationRepository
from points_v2.data.points_repo import PointsRepository
from points_v2.data.user_repo import UserRepository

__all__ = [
    "JsonRepository",
    "UserRepository",
    "PointsRepository",
    "AuditRepository",
    "NotificationRepository",
]
