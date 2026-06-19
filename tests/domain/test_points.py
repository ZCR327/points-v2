"""Tests for points_v2.domain.points."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from points_v2.domain.enums import OperationType
from points_v2.domain.points import (
    PointsAdjustment,
    PointsRecord,
    UserRanking,
)


def test_points_record_defaults_and_immutable_shape() -> None:
    """默认 id / created_at；amount 必为正。"""
    rec = PointsRecord(
        user_id="u1",
        operation=OperationType.EARN,
        amount=10,
        balance_after=10,
    )
    assert rec.id
    assert rec.created_at is not None
    assert rec.amount == 10
    assert rec.operator_id is None


def test_points_record_amount_must_be_positive() -> None:
    """amount 0 / 负数应被拒。"""
    with pytest.raises(ValidationError):
        PointsRecord(
            user_id="u1",
            operation=OperationType.EARN,
            amount=0,
            balance_after=0,
        )
    with pytest.raises(ValidationError):
        PointsRecord(
            user_id="u1",
            operation=OperationType.EARN,
            amount=-1,
            balance_after=0,
        )


def test_points_adjustment_required_fields() -> None:
    """``PointsAdjustment`` 是 service 层输入 schema。"""
    adj = PointsAdjustment(user_id="u1", amount=5, reason="recycle")
    assert adj.user_id == "u1"
    assert adj.amount == 5
    assert adj.reason == "recycle"
    # 缺 user_id 抛错
    with pytest.raises(ValidationError):
        PointsAdjustment(amount=5)  # type: ignore[call-arg]


def test_user_ranking_validates_rank_and_total() -> None:
    """``UserRanking`` rank >= 1、total_points >= 0。"""
    rank = UserRanking(
        rank=1,
        user_id="u1",
        username="alice",
        display_name="Alice",
        total_points=100,
        period="week",
    )
    assert rank.rank == 1
    assert rank.period == "week"
    with pytest.raises(ValidationError):
        UserRanking(
            rank=0,  # invalid
            user_id="u1",
            username="alice",
            display_name="Alice",
            total_points=0,
            period="all",
        )
    with pytest.raises(ValidationError):
        UserRanking(
            rank=1,
            user_id="u1",
            username="alice",
            display_name="Alice",
            total_points=-1,
            period="all",
        )
