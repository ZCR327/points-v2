"""User domain models (ARCHITECTURE §5.1).

- :class:`User`: 完整领域模型（持久化层 / API 响应）
- :class:`UserCreate`: 接收新用户输入（密码明文）
- :class:`UserUpdate`: 部分更新（所有字段可选）

Pydantic v2 配置：
- ``model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)``
- 时间字段统一 UTC ``datetime``，存储用 ``isoformat``
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from points_v2.domain.enums import UserRole

# ---------------------------------------------------------------------------
# 验证常量
# ---------------------------------------------------------------------------
USERNAME_MIN = 3
USERNAME_MAX = 32
DISPLAY_NAME_MAX = 64

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def _utcnow() -> datetime:
    """UTC 当前时间（带时区），避免本地时间导致序列化歧义。"""
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# 共享字段类型
# ---------------------------------------------------------------------------
Username = Annotated[
    str,
    Field(min_length=USERNAME_MIN, max_length=USERNAME_MAX),
]
DisplayName = Annotated[
    str,
    Field(min_length=1, max_length=DISPLAY_NAME_MAX),
]


# ---------------------------------------------------------------------------
# 主模型
# ---------------------------------------------------------------------------
class User(BaseModel):
    """领域模型：完整用户。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(default_factory=_new_id)
    username: Username
    display_name: DisplayName
    role: UserRole = UserRole.USER
    points: int = Field(default=0, ge=0)
    password_hash: str = Field(min_length=1)
    is_active: bool = True
    is_locked: bool = False
    failed_login_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    last_login_at: datetime | None = None

    # ------------------------------------------------------------------ 验证
    @field_validator("username")
    @classmethod
    def _username_format(cls, value: str) -> str:
        if not _USERNAME_RE.match(value):
            raise ValueError(
                "用户名只能包含字母、数字、下划线、点、短横线",
            )
        return value

    # ------------------------------------------------------------------ 行为
    def touch(self) -> None:
        """刷新 ``updated_at``。在 repository.save() 前调用。"""
        self.updated_at = _utcnow()


class UserCreate(BaseModel):
    """创建用户时的输入 schema（明文密码）。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    username: Username
    display_name: DisplayName
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.USER
    initial_points: int = Field(default=0, ge=0)

    @field_validator("username")
    @classmethod
    def _username_format(cls, value: str) -> str:
        if not _USERNAME_RE.match(value):
            raise ValueError(
                "用户名只能包含字母、数字、下划线、点、短横线",
            )
        return value


class UserUpdate(BaseModel):
    """部分更新：所有字段可选，至少传一个。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: DisplayName | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    is_locked: bool | None = None
    points: int | None = Field(default=None, ge=0)

    def has_any(self) -> bool:
        """返回 ``True`` 当至少一个字段被显式设置。"""
        return any(
            getattr(self, name) is not None
            for name in ("display_name", "role", "is_active", "is_locked", "points")
        )


__all__ = [
    "User",
    "UserCreate",
    "UserUpdate",
]
