"""Notification domain models (ARCHITECTURE §5.1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from points_v2.domain.enums import NotificationLevel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


class Notification(BaseModel):
    """系统通知 / 消息。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(default_factory=_new_id)
    user_id: str | None = None  # None = 全员
    level: NotificationLevel = NotificationLevel.INFO
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=2000)
    is_read: bool = False
    created_at: datetime = Field(default_factory=_utcnow)


__all__ = ["Notification"]
