"""Pydantic schemas for the HTTP API.

设计要点
--------

- 与 ``domain/`` 区分：API schema 关心**序列化 / 输入校验**；domain 关心**业务不变式**
- 字段命名以 ``snake_case`` 为主；API 用 ``alias_generator=to_camel`` 在输出时转 camelCase
  （FastAPI 自动在 OpenAPI 中显示）
- 输入 schema 用 ``extra="forbid"``：多余字段直接 422 而不是被默默忽略
- 错误响应统一格式见 :class:`ErrorResponse`
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from points_v2.domain.enums import (
    AuditAction,
    NotificationLevel,
    OperationType,
    UserRole,
)
from points_v2.domain.user import USERNAME_MAX

# ---------------------------------------------------------------------------
# 通用别名
# ---------------------------------------------------------------------------
NonEmptyStr = Annotated[str, Field(min_length=1, max_length=200)]
PasswordStr = Annotated[str, Field(min_length=8, max_length=128)]
UsernameStr = Annotated[str, Field(min_length=3, max_length=USERNAME_MAX)]
Amount = Annotated[int, Field(ge=1, le=1_000_000_000)]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    username: UsernameStr
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    expires_at: datetime
    user_id: str
    username: str
    role: UserRole


class UserInfoResponse(BaseModel):
    """``GET /api/auth/me`` 响应。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    username: str
    display_name: str
    role: UserRole
    points: int
    is_active: bool
    is_locked: bool
    created_at: datetime
    last_login_at: datetime | None


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
class UserCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    username: UsernameStr
    display_name: NonEmptyStr
    password: PasswordStr
    role: UserRole = UserRole.USER
    initial_points: int = Field(default=0, ge=0)


class UserUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: NonEmptyStr | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    is_locked: bool | None = None
    points: int | None = Field(default=None, ge=0)

    def has_any(self) -> bool:
        return any(
            getattr(self, f) is not None
            for f in ("display_name", "role", "is_active", "is_locked", "points")
        )


class UserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    username: str
    display_name: str
    role: UserRole
    points: int
    is_active: bool
    is_locked: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None


# ---------------------------------------------------------------------------
# Points
# ---------------------------------------------------------------------------
class PointsAddRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_id: str = Field(min_length=1)
    amount: Amount
    reason: str = Field(default="", max_length=500)


class PointsDeductRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_id: str = Field(min_length=1)
    amount: Amount
    reason: str = Field(default="", max_length=500)


class PointsTransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    from_user_id: str = Field(min_length=1, alias="fromUserId")
    to_user_id: str = Field(min_length=1, alias="toUserId")
    amount: Amount
    reason: str = Field(default="", max_length=500)

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )


class PointsBalanceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    username: str
    points: int


class PointsRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    user_id: str
    operation: OperationType
    amount: int
    balance_after: int
    reason: str
    operator_id: str | None
    created_at: datetime


class PointsHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    total: int
    records: list[PointsRecordResponse]


# ---------------------------------------------------------------------------
# Rankings & Stats
# ---------------------------------------------------------------------------
class RankingItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int
    user_id: str
    username: str
    display_name: str
    total_points: int
    period: str


class RankingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: str
    items: list[RankingItemResponse]


class SystemStatsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_count: int
    total_points: int
    record_count: int
    max_balance: int
    min_balance: int


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
class AuditQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str | None = None
    action: str | AuditAction | None = None
    resource: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=500)


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    user_id: str | None
    action: str
    resource: str | None
    details: dict[str, Any]
    ip_address: str | None
    created_at: datetime


class AuditListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    items: list[AuditLogResponse]


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
class NotificationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    level: NotificationLevel = NotificationLevel.INFO
    title: NonEmptyStr
    content: str = Field(default="", max_length=2000)
    user_id: str | None = None  # None = 全员广播


class NotificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    user_id: str | None
    level: NotificationLevel
    title: str
    content: str
    is_read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    items: list[NotificationResponse]


# ---------------------------------------------------------------------------
# Change password
# ---------------------------------------------------------------------------
class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    old_password: str = Field(min_length=1, max_length=128)
    new_password: PasswordStr


# ---------------------------------------------------------------------------
# Lock / Unlock
# ---------------------------------------------------------------------------
class LockUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(default="", max_length=500)


# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------
class SuccessResponse(BaseModel):
    """通用成功响应（无数据）。"""

    model_config = ConfigDict(extra="forbid")

    ok: Literal[True] = True
    message: str = "ok"


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """统一错误响应（ARCHITECTURE §8.3）。"""

    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail


__all__ = [
    "Amount",
    "UsernameStr",
    "PasswordStr",
    "NonEmptyStr",
    "LoginRequest",
    "LoginResponse",
    "UserInfoResponse",
    "UserCreateRequest",
    "UserUpdateRequest",
    "UserResponse",
    "PointsAddRequest",
    "PointsDeductRequest",
    "PointsTransferRequest",
    "PointsBalanceResponse",
    "PointsRecordResponse",
    "PointsHistoryResponse",
    "RankingItemResponse",
    "RankingResponse",
    "SystemStatsResponse",
    "AuditQueryRequest",
    "AuditLogResponse",
    "AuditListResponse",
    "NotificationCreateRequest",
    "NotificationResponse",
    "NotificationListResponse",
    "ChangePasswordRequest",
    "LockUserRequest",
    "SuccessResponse",
    "ErrorResponse",
    "ErrorDetail",
]
