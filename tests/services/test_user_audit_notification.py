"""Tests for UserService (CRUD / lock / unlock) + AuditService + NotificationService."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from points_v2.core.exceptions import DuplicateUserError, UserNotFoundError
from points_v2.data import AuditRepository, NotificationRepository
from points_v2.data.user_repo import UserRepository
from points_v2.domain.audit import AuditFilter
from points_v2.domain.enums import AuditAction, NotificationLevel, UserRole
from points_v2.domain.user import UserCreate, UserUpdate
from points_v2.services.audit_service import AuditService
from points_v2.services.notification_service import NotificationService
from points_v2.services.user_service import UserService


def _build_user_svc(tmp_data_dir):
    repo = UserRepository()
    return UserService(repo), repo


def _make(svc, username, role=UserRole.USER, points=0, password="TestPass123"):
    return svc.create(
        UserCreate(
            username=username,
            display_name=username.title(),
            password=password,
            role=role,
            initial_points=points,
        ),
    )


# ---------------------------------------------------------------------------
# UserService
# ---------------------------------------------------------------------------
def test_user_create_rejects_duplicate_username(tmp_data_dir) -> None:
    svc, _ = _build_user_svc(tmp_data_dir)
    _make(svc, "alice")
    with pytest.raises(DuplicateUserError):
        _make(svc, "alice")


def test_user_create_rejects_short_username(tmp_data_dir) -> None:
    """Service 必须自己守住长度下限 — 越过 Pydantic 也能拒（防御性深度）"""
    svc, _ = _build_user_svc(tmp_data_dir)
    with pytest.raises(ValueError, match="长度"):
        # 绕过 Pydantic 校验,验证 service 层显式防御
        raw = UserCreate.model_construct(
            username="ab",
            display_name="AB",
            password="TestPass123",
        )
        svc.create(raw)


def test_user_get_by_id_and_by_username(tmp_data_dir) -> None:
    svc, _ = _build_user_svc(tmp_data_dir)
    user = _make(svc, "alice")
    assert svc.get_by_id(user.id).username == "alice"
    assert svc.get_by_username("alice").id == user.id
    with pytest.raises(UserNotFoundError):
        svc.get_by_id("nope")
    with pytest.raises(UserNotFoundError):
        svc.get_by_username("ghost")


def test_user_list_pagination_and_sort(tmp_data_dir) -> None:
    svc, _ = _build_user_svc(tmp_data_dir)
    for name in ("charlie", "alice", "bob"):
        _make(svc, name)
    page = svc.list(offset=0, limit=2)
    assert len(page) == 2
    assert page[0].username == "alice"  # 字典序
    assert page[1].username == "bob"
    with pytest.raises(ValueError):
        svc.list(offset=-1)
    with pytest.raises(ValueError):
        svc.list(limit=0)


def test_user_update_partial_and_empty(tmp_data_dir) -> None:
    svc, repo = _build_user_svc(tmp_data_dir)
    user = _make(svc, "alice", points=10)
    updated = svc.update(
        user.id,
        UserUpdate(display_name="AliceNew", points=99),
    )
    assert updated.display_name == "AliceNew"
    assert updated.points == 99
    assert repo.get(user.id).points == 99
    # 空更新
    with pytest.raises(ValueError, match="至少"):
        svc.update(user.id, UserUpdate())


def test_user_delete_removes(tmp_data_dir) -> None:
    svc, repo = _build_user_svc(tmp_data_dir)
    user = _make(svc, "alice")
    svc.delete(user.id)
    assert repo.get(user.id) is None
    with pytest.raises(UserNotFoundError):
        svc.delete(user.id)


def test_user_lock_and_unlock(tmp_data_dir) -> None:
    svc, repo = _build_user_svc(tmp_data_dir)
    user = _make(svc, "alice")
    locked = svc.lock(user.id, reason="too many failures")
    assert locked.is_locked is True
    # 重复 lock 幂等
    assert svc.lock(user.id).is_locked is True
    # 解锁
    unlocked = svc.unlock(user.id)
    assert unlocked.is_locked is False
    assert repo.get(user.id).failed_login_count == 0


# ---------------------------------------------------------------------------
# AuditService
# ---------------------------------------------------------------------------
def test_audit_log_and_query(tmp_data_dir) -> None:
    repo = AuditRepository()
    svc = AuditService(repo)
    log = svc.log(
        "user.create",
        user_id="u1",
        resource="u2",
        details={"k": "v"},
        ip_address="127.0.0.1",
    )
    assert log.id
    assert log.action_str == "user.create"
    flt = AuditFilter(action="user.create", limit=10)
    rows = svc.query(flt)
    assert len(rows) == 1
    assert rows[0].id == log.id


def test_audit_get_user_actions_filters_by_user_and_days(tmp_data_dir) -> None:
    repo = AuditRepository()
    svc = AuditService(repo)
    svc.log("user.create", user_id="u1", resource=None, details=None)
    svc.log("user.login", user_id="u1", resource=None, details=None)
    svc.log("user.create", user_id="u2", resource=None, details=None)
    rows = svc.get_user_actions("u1", days=7, limit=50)
    assert len(rows) == 2
    assert all(r.user_id == "u1" for r in rows)


def test_audit_log_rejects_empty_action(tmp_data_dir) -> None:
    repo = AuditRepository()
    svc = AuditService(repo)
    with pytest.raises(ValueError, match="action"):
        svc.log("", user_id=None)


def test_audit_query_rejects_non_filter(tmp_data_dir) -> None:
    repo = AuditRepository()
    svc = AuditService(repo)
    with pytest.raises(TypeError):
        svc.query("not-a-filter")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# NotificationService
# ---------------------------------------------------------------------------
def test_notification_create_list_and_mark_read(tmp_data_dir) -> None:
    user_repo = UserRepository()
    note_repo = NotificationRepository()
    svc = NotificationService(note_repo, user_repo)
    # 全局广播
    n_global = svc.create(
        NotificationLevel.INFO,
        "系统通知",
        "v2 上线",
        user_id=None,
    )
    assert n_global.user_id is None
    rows = svc.list_for_user("anyone", include_global=True, limit=10)
    assert any(n.id == n_global.id for n in rows)
    # 标记已读
    assert svc.mark_read(n_global.id) is True
    # 重复标记返回 False
    assert svc.mark_read(n_global.id) is False


def test_notification_rejects_empty_title(tmp_data_dir) -> None:
    note_repo = NotificationRepository()
    svc = NotificationService(note_repo)
    with pytest.raises(ValueError, match="title"):
        svc.create(NotificationLevel.WARNING, "", "x")


def test_notification_broadcast_is_global(tmp_data_dir) -> None:
    note_repo = NotificationRepository()
    svc = NotificationService(note_repo)
    n = svc.broadcast(NotificationLevel.ERROR, "告警", "disk full")
    assert n.user_id is None
    assert n.level is NotificationLevel.ERROR
