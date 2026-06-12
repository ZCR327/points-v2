"""Audit domain models (ARCHITECTURE §5.1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from points_v2.domain.enums import AuditAction


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
class AuditLog(BaseModel):
    """不可变审计日志条目。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(default_factory=_new_id)
    user_id: str | None = None
    action: str | AuditAction
    resource: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    ip_address: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)

    @property
    def action_str(self) -> str:
        """始终返回字符串形式的 action（方便存储 / 检索）。"""
        if isinstance(self.action, AuditAction):
            return self.action.value
        return str(self.action)


# ---------------------------------------------------------------------------
# 分页/过滤：使用 Annotated 类型定义清晰的边界
# ---------------------------------------------------------------------------
PositiveInt = Annotated[int, Field(ge=1)]
NonNegativeInt = Annotated[int, Field(ge=0)]


class AuditFilter(BaseModel):
    """审计查询过滤器。"""

    model_config = ConfigDict(extra="forbid")

    user_id: str | None = None
    action: str | AuditAction | None = None
    resource: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    offset: NonNegativeInt = 0
    limit: PositiveInt = 50

    @property
    def action_str(self) -> str | None:
        if isinstance(self.action, AuditAction):
            return self.action.value
        return self.action


__all__ = [
    "AuditLog",
    "AuditFilter",
]
