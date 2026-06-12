"""Tests for points_v2.data.user_repo."""

from __future__ import annotations

import pytest

from points_v2.data.user_repo import UserRepository
from points_v2.domain.enums import UserRole
from points_v2.domain.user import User


def _make_user(username: str, role: UserRole = UserRole.USER, points: int = 0) -> User:
    return User(
        username=username,
        display_name=username.title(),
        password_hash="x" * 60,
        role=role,
        points=points,
    )


def test_insert_and_get(tmp_data_dir) -> None:
    """``insert`` 后 ``get`` 能取回同一对象。"""
    repo = UserRepository()
    user = _make_user("alice")
    repo.insert(user)
    assert repo.get(user.id) is not None
    assert repo.get(user.id).username == "alice"
    assert repo.count() == 1


def test_insert_duplicate_pk_raises(tmp_data_dir) -> None:
    """重复主键应抛 ``ValueError``。"""
    repo = UserRepository()
    user = _make_user("alice")
    repo.insert(user)
    with pytest.raises(ValueError, match="已存在"):
        repo.insert(user)


def test_get_by_username(tmp_data_dir) -> None:
    """``get_by_username`` 按用户名精确匹配。"""
    repo = UserRepository()
    a = _make_user("alice")
    b = _make_user("bob")
    repo.insert(a)
    repo.insert(b)
    assert repo.get_by_username("alice").id == a.id
    assert repo.get_by_username("missing") is None


def test_delete_returns_bool(tmp_data_dir) -> None:
    """``delete`` 返回 ``True`` 当真删了，``False`` 当 pk 不存在。"""
    repo = UserRepository()
    user = _make_user("alice")
    repo.insert(user)
    assert repo.delete(user.id) is True
    assert repo.delete(user.id) is False


def test_update_replaces_object(tmp_data_dir) -> None:
    """``update`` 用同 pk 的新对象替换；按对象字段获取最新值。"""
    repo = UserRepository()
    user = _make_user("alice", points=10)
    repo.insert(user)
    new = user.model_copy(update={"points": 99})
    new.touch()
    repo.update(new)
    assert repo.get(user.id).points == 99


def test_atomic_write_then_reload(tmp_data_dir) -> None:
    """写入后再新建一个 repo 读盘，应能拿回相同数据。"""
    repo1 = UserRepository()
    user = _make_user("alice", role=UserRole.ADMIN, points=50)
    repo1.insert(user)
    # 新建实例 —— 模拟重启
    repo2 = UserRepository()
    repo2.load()
    loaded = repo2.get(user.id)
    assert loaded is not None
    assert loaded.username == "alice"
    assert loaded.role is UserRole.ADMIN
    assert loaded.points == 50
    # 实际文件应存在
    assert (tmp_data_dir / "users.json").exists()


def test_update_points_changes_balance(tmp_data_dir) -> None:
    """``update_points`` 改余额并更新 updated_at。"""
    repo = UserRepository()
    user = _make_user("alice", points=10)
    repo.insert(user)
    original_updated_at = user.updated_at
    updated = repo.update_points(user.id, 99)
    assert updated.points == 99
    # updated_at 至少应在原值之后（微秒可能相同，>= 即可）
    assert updated.updated_at >= original_updated_at
    # 找不到时抛 KeyError
    with pytest.raises(KeyError):
        repo.update_points("missing", 1)


def test_is_username_taken_with_exclude(tmp_data_dir) -> None:
    """``is_username_taken`` 支持 exclude_id（用于更新场景）。"""
    repo = UserRepository()
    a = _make_user("alice")
    b = _make_user("bob")
    repo.insert(a)
    repo.insert(b)
    assert repo.is_username_taken("alice") is True
    # 排除自己 → False
    assert repo.is_username_taken("alice", exclude_id=a.id) is False
    assert repo.is_username_taken("nobody") is False


def test_get_by_role_and_active(tmp_data_dir) -> None:
    """``get_by_role`` / ``get_active`` 业务查询。"""
    repo = UserRepository()
    admin = _make_user("admin1", role=UserRole.ADMIN)
    user = _make_user("alice", role=UserRole.USER)
    locked = _make_user("bob", role=UserRole.USER, points=0)
    locked = locked.model_copy(update={"is_locked": True})
    inactive = _make_user("carol", role=UserRole.USER)
    inactive = inactive.model_copy(update={"is_active": False})
    repo.insert(admin)
    repo.insert(user)
    repo.insert(locked)
    repo.insert(inactive)
    admins = repo.get_by_role(UserRole.ADMIN)
    assert len(admins) == 1
    # get_active 要求 is_active 且 not is_locked
    active = repo.get_active()
    assert {u.username for u in active} == {"admin1", "alice"}
    assert repo.count_by_role(UserRole.USER) == 3
