"""Business service layer (ARCHITECTURE §7).

依赖方向：``core`` + ``domain`` + ``data`` + ``utils`` ← ``services``
（service 不依赖 api / ui）。
"""

from __future__ import annotations

from points_v2.services import (
    audit_service,
    auth_service,
    notification_service,
    points_service,
    user_service,
)
from points_v2.services.audit_service import AuditService
from points_v2.services.auth_service import AuthService, AuthToken
from points_v2.services.notification_service import NotificationService
from points_v2.services.points_service import PointsService
from points_v2.services.user_service import UserService

__all__ = [
    "AuthService",
    "AuthToken",
    "UserService",
    "PointsService",
    "AuditService",
    "NotificationService",
    # modules
    "audit_service",
    "auth_service",
    "notification_service",
    "points_service",
    "user_service",
]
