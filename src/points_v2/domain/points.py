"""Points domain models (ARCHITECTURE §5.1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from points_v2.domain.enums import OperationType

# 数量上限：单笔最大 1e9 ——防止溢出/脏数据
MAX_AMOUNT: int = 1_000_000_000


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


PositiveInt = Annotated[int, Field(ge=1, le=MAX_AMOUNT)]
NonNegativeInt = Annotated[int, Field(ge=0, le=MAX_AMOUNT)]


# ---------------------------------------------------------------------------
class PointsRecord(BaseModel):
    """不可变积分流水。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(default_factory=_new_id)
    user_id: str = Field(min_length=1)
    operation: OperationType
    amount: PositiveInt
    balance_after: NonNegativeInt
    reason: str = Field(default="", max_length=500)
    operator_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
class PointsAdjustment(BaseModel):
    """加减积分的输入 schema（service 层消费）。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_id: str = Field(min_length=1)
    amount: PositiveInt
    reason: str = Field(default="", max_length=500)
    operator_id: str | None = None


# ---------------------------------------------------------------------------
class UserRanking(BaseModel):
    """排行榜单行（ARCHITECTURE §7 PointsService.get_ranking）。"""

    model_config = ConfigDict(extra="forbid")

    rank: int = Field(ge=1)
    user_id: str
    username: str
    display_name: str
    total_points: int = Field(ge=0)
    period: str  # "week" / "month" / "all"


__all__ = [
    "PointsRecord",
    "PointsAdjustment",
    "UserRanking",
    "MAX_AMOUNT",
]
