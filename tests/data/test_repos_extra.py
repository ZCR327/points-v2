"""Additional data layer tests for coverage >= 80%."""

from __future__ import annotations

from points_v2.data.audit_repo import AuditRepository
from points_v2.data.notification_repo import NotificationRepository
from points_v2.data.points_repo import PointsRepository
from points_v2.domain.audit import AuditFilter, AuditLog
from points_v2.domain.enums import (
    AuditAction,
    NotificationLevel,
    OperationType,
)
from points_v2.domain.notification import Notification
from points_v2.domain.points import PointsRecord


# ---------------------------------------------------------------------------
# PointsRepository
# ---------------------------------------------------------------------------
def _make_record(user_id: str, amount: int, op: OperationType = OperationType.EARN) -> PointsRecord:
    return PointsRecord(
        user_id=user_id,
        operation=op,
        amount=amount,
        balance_after=amount,
    )


def test_points_repo_insert_and_get_by_user(tmp_data_dir) -> None:
    """``get_by_user`` 只返回该用户的记录。"""
    repo = PointsRepository()
    r1 = _make_record("u1", 10)
    r2 = _make_record("u1", 5)
    r3 = _make_record("u2", 100)
    repo.insert(r1)
    repo.insert(r2)
    repo.insert(r3)
    u1_records = repo.get_by_user("u1")
    assert len(u1_records) == 2
    # 两条都返回（顺序不强制断言——同微秒内 created_at 相同）
    amounts = {r.amount for r in u1_records}
    assert amounts == {5, 10}


def test_points_repo_filter_by_operation_and_limit(tmp_data_dir) -> None:
    """``operation`` 过滤 + ``limit`` 限制返回数量。"""
    repo = PointsRepository()
    repo.insert(_make_record("u1", 10, OperationType.EARN))
    repo.insert(_make_record("u1", 5, OperationType.SPEND))
    repo.insert(_make_record("u1", 7, OperationType.EARN))
    earns = repo.get_by_user("u1", operation=OperationType.EARN)
    assert len(earns) == 2
    # 限制 1 条
    assert len(repo.get_by_user("u1", limit=1)) == 1


def test_points_repo_total_earned_and_ranking(tmp_data_dir) -> None:
    """``total_earned`` 累加；``ranking`` 按总额降序。"""
    repo = PointsRepository()
    repo.insert(_make_record("alice", 10))
    repo.insert(_make_record("alice", 20))
    repo.insert(_make_record("bob", 100))
    assert repo.total_earned("alice") == 30
    assert repo.total_earned("bob") == 100
    assert repo.total_earned("nobody") == 0

    ranked = repo.ranking(limit=10)
    assert ranked[0] == ("bob", 100)
    assert ranked[1] == ("alice", 30)


def test_points_repo_recent_days(tmp_data_dir) -> None:
    """``recent_days(0)`` 返回空（防止时间边界错误）。"""
    repo = PointsRepository()
    repo.insert(_make_record("u1", 10))
    assert repo.recent_days("u1", 0) == []
    # days=1 应至少能取到刚才这条
    assert len(repo.recent_days("u1", 1)) == 1


# ---------------------------------------------------------------------------
# AuditRepository
# ---------------------------------------------------------------------------
def test_audit_repo_insert_and_query(tmp_data_dir) -> None:
    """``insert`` + ``query`` 基本流程。"""
    repo = AuditRepository()
    log1 = AuditLog(
        user_id="u1", action=AuditAction.USER_LOGIN, resource="u1", details={"ip": "1.1.1.1"},
    )
    log2 = AuditLog(
        user_id="u2", action=AuditAction.POINTS_ADD, resource="u2", details={"amount": 5},
    )
    repo.insert(log1)
    repo.insert(log2)
    assert repo.count() == 2

    # 按 user_id 过滤
    only_u1 = repo.query(AuditFilter(user_id="u1", limit=10))
    assert len(only_u1) == 1
    assert only_u1[0].action_str == "user.login"

    # 按 action 过滤
    add_only = repo.query(AuditFilter(action="points.add", limit=10))
    assert len(add_only) == 1
    assert add_only[0].user_id == "u2"


def test_audit_repo_get_by_user(tmp_data_dir) -> None:
    """``get_by_user`` 返回该用户日志、倒序。"""
    repo = AuditRepository()
    for i in range(3):
        repo.insert(AuditLog(user_id="u1", action=f"test.action.{i}"))
    repo.insert(AuditLog(user_id="u2", action="other"))
    u1_logs = repo.get_by_user("u1")
    assert len(u1_logs) == 3


def test_audit_repo_filter_resource(tmp_data_dir) -> None:
    """``resource`` 过滤。"""
    repo = AuditRepository()
    repo.insert(AuditLog(user_id="u1", action="x", resource="res-1"))
    repo.insert(AuditLog(user_id="u1", action="x", resource="res-2"))
    res1 = repo.query(AuditFilter(resource="res-1", limit=10))
    assert len(res1) == 1
    assert res1[0].resource == "res-1"


# ---------------------------------------------------------------------------
# NotificationRepository
# ---------------------------------------------------------------------------
def test_notification_repo_insert_and_list_for_user(tmp_data_dir) -> None:
    """``list_for_user`` 收件人为该用户 + (可选) 全局通知。"""
    repo = NotificationRepository()
    n_personal = Notification(
        user_id="u1", level=NotificationLevel.INFO, title="hi", content="c",
    )
    n_global = Notification(
        user_id=None, level=NotificationLevel.WARNING, title="warn", content="w",
    )
    n_other = Notification(
        user_id="u2", level=NotificationLevel.ERROR, title="err", content="e",
    )
    repo.insert(n_personal)
    repo.insert(n_global)
    repo.insert(n_other)
    # u1 应收到 personal + global
    u1_list = repo.list_for_user("u1", include_global=True, limit=10)
    assert len(u1_list) == 2
    # 排除 global 时只有 personal
    u1_no_global = repo.list_for_user("u1", include_global=False, limit=10)
    assert len(u1_no_global) == 1
    assert u1_no_global[0].id == n_personal.id


def test_notification_repo_mark_read(tmp_data_dir) -> None:
    """``mark_read`` 第一次返回 ``True``，第二次 ``False``。"""
    repo = NotificationRepository()
    n = Notification(user_id="u1", level=NotificationLevel.INFO, title="x", content="y")
    repo.insert(n)
    assert repo.mark_read(n.id) is True
    assert repo.mark_read(n.id) is False
    # 不存在返回 False
    assert repo.mark_read("nope") is False


def test_notification_repo_unread_filter_and_broadcast(tmp_data_dir) -> None:
    """``unread_only`` 过滤 + ``global_broadcast`` 列出全部全局通知。"""
    repo = NotificationRepository()
    n1 = Notification(user_id="u1", level=NotificationLevel.INFO, title="a", content="b")
    n2 = Notification(user_id=None, level=NotificationLevel.WARNING, title="c", content="d")
    repo.insert(n1)
    repo.insert(n2)
    repo.mark_read(n1.id)
    # u1 未读过滤：只有 global n2
    unread = repo.list_for_user("u1", include_global=True, unread_only=True, limit=10)
    assert len(unread) == 1
    assert unread[0].id == n2.id
    # global_broadcast
    broadcasts = repo.global_broadcast()
    assert len(broadcasts) == 1
    assert broadcasts[0].id == n2.id
