"""Enumerations used across domain and service layers.

All enums inherit from :class:`str, Enum` so they serialize cleanly to JSON and YAML
without ``enum`` quirks.  String values are the **canonical wire / storage format**.
"""

from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    """User permission tier (ARCHITECTURE §5.1).

    排序与权限强度一致：``SUPER_ADMIN > ADMIN > OPERATOR > USER``。
    """

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    OPERATOR = "operator"
    USER = "user"

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]


class OperationType(str, Enum):
    """Points operation category (ARCHITECTURE §5.1)."""

    EARN = "earn"
    SPEND = "spend"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    ADJUST = "adjust"
    REFUND = "refund"

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]


class NotificationLevel(str, Enum):
    """Notification severity (ARCHITECTURE §5.1)."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]


class AuditAction(str, Enum):
    """Well-known audit actions.

    **非封闭列表**：审计系统接受任意字符串，但常见动作在此枚举以便 IDE 自动补全。
    """

    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_LOCK = "user.lock"
    USER_UNLOCK = "user.unlock"
    USER_LOGIN = "user.login"
    USER_LOGIN_FAIL = "user.login_fail"
    POINTS_ADD = "points.add"
    POINTS_DEDUCT = "points.deduct"
    POINTS_TRANSFER = "points.transfer"
    POINTS_ADJUST = "points.adjust"
    NOTIFICATION_BROADCAST = "notification.broadcast"
    CONFIG_RELOAD = "config.reload"

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]


__all__ = [
    "UserRole",
    "OperationType",
    "NotificationLevel",
    "AuditAction",
]
