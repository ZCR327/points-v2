"""Domain layer: Pydantic models and enums.

依赖方向：``core`` ← ``domain``（domain 不依赖任何上层模块）。
"""

from __future__ import annotations

from points_v2.domain.audit import AuditFilter, AuditLog
from points_v2.domain.enums import (
    AuditAction,
    NotificationLevel,
    OperationType,
    UserRole,
)
from points_v2.domain.notification import Notification
from points_v2.domain.points import (
    MAX_AMOUNT,
    PointsAdjustment,
    PointsRecord,
    UserRanking,
)
from points_v2.domain.user import User, UserCreate, UserUpdate

__all__ = [
    # enums
    "UserRole",
    "OperationType",
    "NotificationLevel",
    "AuditAction",
    # user
    "User",
    "UserCreate",
    "UserUpdate",
    # points
    "PointsRecord",
    "PointsAdjustment",
    "UserRanking",
    "MAX_AMOUNT",
    # audit
    "AuditLog",
    "AuditFilter",
    # notification
    "Notification",
]
