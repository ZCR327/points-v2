"""Tests for PointsService (add / deduct / transfer / history / ranking / stats)."""

from __future__ import annotations

import pytest

from points_v2.core.exceptions import InsufficientPointsError
from points_v2.data.points_repo import PointsRepository
from points_v2.data.user_repo import UserRepository
from points_v2.domain.enums import OperationType, UserRole
from points_v2.domain.user import UserCreate
from points_v2.services.points_service import PointsService
from points_v2.services.user_service import UserService


def _build(tmp_data_dir):
    user_repo = UserRepository()
    points_repo = PointsRepository()
    user_svc = UserService(user_repo)
    points_svc = PointsService(user_repo, points_repo)
    return user_svc, points_svc, user_repo, points_repo


def _make(user_svc, username, role=UserRole.USER, points=0, password="TestPass123"):
    return user_svc.create(
        UserCreate(
            username=username,
            display_name=username.title(),
            password=password,
            role=role,
            initial_points=points,
        ),
    )


# ---------------------------------------------------------------------------
# 8 个测试
# ---------------------------------------------------------------------------
def test_add_creates_record_and_increments_balance(tmp_data_dir) -> None:
    """add 写一条 EARN 流水，余额增加。"""
    user_svc, points_svc, user_repo, points_repo = _build(tmp_data_dir)
    user = _make(user_svc, "alice", points=10)
    rec = points_svc.add(user.id, 25, reason="回收", operator_id="admin1")
    assert rec.operation is OperationType.EARN
    assert rec.amount == 25
    assert rec.balance_after == 35
    assert user_repo.get(user.id).points == 35
    assert points_repo.count() == 1


def test_deduct_rejects_when_balance_insufficient(tmp_data_dir) -> None:
    """扣减时余额不足 → InsufficientPointsError（带 balance / required 详情）。"""
    user_svc, points_svc, _, _ = _build(tmp_data_dir)
    user = _make(user_svc, "alice", points=10)
    with pytest.raises(InsufficientPointsError) as exc_info:
        points_svc.deduct(user.id, 50, reason="消费")
    assert exc_info.value.details["balance"] == 10
    assert exc_info.value.details["required"] == 50


def test_deduct_success_writes_spend_record(tmp_data_dir) -> None:
    """扣减成功写 SPEND 流水。"""
    user_svc, points_svc, user_repo, points_repo = _build(tmp_data_dir)
    user = _make(user_svc, "alice", points=100)
    rec = points_svc.deduct(user.id, 30, reason="商城")
    assert rec.operation is OperationType.SPEND
    assert rec.balance_after == 70
    assert user_repo.get(user.id).points == 70
    assert points_repo.count() == 1


def test_transfer_between_users_writes_two_records(tmp_data_dir) -> None:
    """转账：两条流水（TRANSFER_OUT + TRANSFER_IN），双方余额同步。"""
    user_svc, points_svc, user_repo, points_repo = _build(tmp_data_dir)
    alice = _make(user_svc, "alice", points=100)
    bob = _make(user_svc, "bob", points=50)
    out, inc = points_svc.transfer(alice.id, bob.id, 30, reason="gift", operator_id="sys")
    assert out.operation is OperationType.TRANSFER_OUT
    assert inc.operation is OperationType.TRANSFER_IN
    assert user_repo.get(alice.id).points == 70
    assert user_repo.get(bob.id).points == 80
    assert points_repo.count() == 2


def test_transfer_to_self_raises_value_error(tmp_data_dir) -> None:
    """自己转自己 → ValueError。"""
    user_svc, points_svc, _, _ = _build(tmp_data_dir)
    alice = _make(user_svc, "alice", points=100)
    with pytest.raises(ValueError, match="不能相同"):
        points_svc.transfer(alice.id, alice.id, 10)


def test_transfer_insufficient_raises(tmp_data_dir) -> None:
    """转账方余额不足 → InsufficientPointsError。"""
    user_svc, points_svc, user_repo, _ = _build(tmp_data_dir)
    alice = _make(user_svc, "alice", points=10)
    bob = _make(user_svc, "bob", points=0)
    with pytest.raises(InsufficientPointsError):
        points_svc.transfer(alice.id, bob.id, 50)
    # 余额不变（事务语义）
    assert user_repo.get(alice.id).points == 10
    assert user_repo.get(bob.id).points == 0


def test_history_returns_user_records_in_desc_order(tmp_data_dir) -> None:
    """get_history 返回该用户流水倒序。"""
    user_svc, points_svc, _, _ = _build(tmp_data_dir)
    alice = _make(user_svc, "alice", points=0)
    points_svc.add(alice.id, 10, reason="1")
    points_svc.add(alice.id, 20, reason="2")
    points_svc.deduct(alice.id, 5, reason="3")
    records = points_svc.get_history(alice.id, days=1, limit=10)
    assert len(records) == 3
    # 时间倒序
    assert records[0].created_at >= records[-1].created_at
    # 只属于 alice
    assert all(r.user_id == alice.id for r in records)


def test_ranking_and_stats_aggregate_correctly(tmp_data_dir) -> None:
    """ranking + stats 聚合正确。"""
    user_svc, points_svc, _, _ = _build(tmp_data_dir)
    a = _make(user_svc, "alice", points=0)
    b = _make(user_svc, "bob", points=0)
    c = _make(user_svc, "carol", points=0)
    points_svc.add(a.id, 100)
    points_svc.add(b.id, 50)
    points_svc.add(c.id, 200)
    ranking = points_svc.get_ranking(period="all", limit=10)
    assert [r.username for r in ranking] == ["carol", "alice", "bob"]
    assert ranking[0].total_points == 200
    assert ranking[0].rank == 1

    stats = points_svc.get_stats()
    assert stats.user_count == 3
    assert stats.total_points == 350  # 当前余额累加
    assert stats.record_count == 3
    assert stats.max_balance == 200
    assert stats.min_balance == 50
