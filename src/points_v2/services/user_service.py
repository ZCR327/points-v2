"""UserService — 用户 CRUD / 锁定 / 改密管理。

设计要点
--------

- ``create`` 走 :class:`domain.user.UserCreate` 校验；密码哈希后存 ``User.password_hash``
- ``update`` 部分字段更新；至少传一个字段（model validator 已保证）
- ``lock`` / ``unlock`` 不影响 ``is_active``——后者是管理员手工停用，与锁定独立
- ``delete`` 不级联清理 sessions；由 auth_service 视情况吊销
- 不直接调其他 service；审计通过 ``audit_service`` 是单向上层组装
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from points_v2.core.exceptions import (
    DuplicateUserError,
    PointsV2Error,
    UserNotFoundError,
)
from points_v2.core.logging import get_logger
from points_v2.domain.user import User, UserCreate, UserUpdate
from points_v2.utils.hashing import hash_password
from points_v2.utils.time import utcnow
from points_v2.utils.validators import validate_username

if TYPE_CHECKING:
    from points_v2.data.user_repo import UserRepository

__all__ = ["UserService"]


class UserService:
    """用户管理服务。"""

    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo
        self._log = get_logger("users")

    # ------------------------------------------------------------------ CRUD
    def create(self, data: UserCreate) -> User:
        """创建用户。失败抛 :class:`DuplicateUserError` / :class:`ValueError`。"""
        username = validate_username(data.username)
        if self._user_repo.is_username_taken(username):
            raise DuplicateUserError(
                f"用户名 {username} 已被占用",
                details={"username": username},
            )
        now = utcnow()
        user = User(
            username=username,
            display_name=data.display_name.strip(),
            password_hash=hash_password(data.password),
            role=data.role,
            points=data.initial_points,
            created_at=now,
            updated_at=now,
        )
        self._user_repo.insert(user)
        self._log.info("创建用户", user_id=user.id, username=user.username, role=user.role.value)
        return user

    def get_by_id(self, user_id: str) -> User:
        """根据 id 取用户。失败抛 :class:`UserNotFoundError`。"""
        user = self._user_repo.get(user_id)
        if user is None:
            raise UserNotFoundError(f"用户 {user_id} 不存在")
        return user

    def get_by_username(self, username: str) -> User:
        """根据用户名取用户。失败抛 :class:`UserNotFoundError`。"""
        normalized = validate_username(username)
        user = self._user_repo.get_by_username(normalized)
        if user is None:
            raise UserNotFoundError(
                f"用户 {username} 不存在",
                details={"username": username},
            )
        return user

    def list(self, *, offset: int = 0, limit: int = 50) -> list[User]:
        """分页列出所有用户（按 username 升序）。"""
        if offset < 0:
            raise ValueError("offset 不能为负")
        if limit <= 0 or limit > 500:
            raise ValueError("limit 必须在 1..500 之间")
        items = sorted(self._user_repo.all(), key=lambda u: u.username)
        return items[offset : offset + limit]

    def update(self, user_id: str, patch: UserUpdate) -> User:
        """部分更新。至少传一个字段（model 限制）。"""
        if not patch.has_any():
            raise ValueError("至少需要更新一个字段")
        user = self.get_by_id(user_id)
        # 收集非 None 字段
        updates: dict[str, object] = {}
        if patch.display_name is not None:
            updates["display_name"] = patch.display_name.strip()
        if patch.role is not None:
            updates["role"] = patch.role
        if patch.is_active is not None:
            updates["is_active"] = patch.is_active
        if patch.is_locked is not None:
            updates["is_locked"] = patch.is_locked
        if patch.points is not None:
            updates["points"] = patch.points
        updated = user.model_copy(update=updates)
        updated.touch()
        self._user_repo.update(updated)
        self._log.info("更新用户", user_id=user_id, fields=list(updates.keys()))
        return updated

    def delete(self, user_id: str) -> None:
        """删除用户；不可恢复。失败抛 :class:`UserNotFoundError`。"""
        user = self.get_by_id(user_id)
        if not self._user_repo.delete(user_id):
            # 理论不会发生——get_by_id 已确认存在
            raise PointsV2Error(f"删除用户 {user_id} 失败")
        self._log.info("删除用户", user_id=user_id, username=user.username)

    def lock(self, user_id: str, reason: str = "") -> User:
        """锁定用户；可附带原因（记录到日志）。"""
        user = self.get_by_id(user_id)
        if user.is_locked:
            return user  # 幂等
        updated = user.model_copy(update={"is_locked": True, "failed_login_count": 0})
        updated.touch()
        self._user_repo.update(updated)
        self._log.info("锁定用户", user_id=user_id, reason=reason or "n/a")
        return updated

    def unlock(self, user_id: str) -> User:
        """解锁用户；清零失败计数。"""
        user = self.get_by_id(user_id)
        if not user.is_locked and user.failed_login_count == 0:
            return user
        updated = user.model_copy(update={"is_locked": False, "failed_login_count": 0})
        updated.touch()
        self._user_repo.update(updated)
        self._log.info("解锁用户", user_id=user_id)
        return updated
