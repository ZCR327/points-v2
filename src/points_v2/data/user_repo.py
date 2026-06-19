"""UserRepository — User 集合的 JSON 持久化。

主要扩展点：
- ``get_by_username(username)`` —— 唯一索引
- ``get_active()`` / ``count_by_role()`` —— 业务查询
"""

from __future__ import annotations

from points_v2.data.base import JsonRepository
from points_v2.domain.enums import UserRole
from points_v2.domain.user import User


class UserRepository(JsonRepository[User]):
    """``data/users.json`` 仓储。"""

    _FILENAME = "users.json"

    def _pk(self, obj: User) -> str:
        return obj.id

    # ------------------------------------------------------------------ 索引
    def get_by_username(self, username: str) -> User | None:
        """按用户名（**精确匹配**）查找。"""
        return self.find_one(lambda u: u.username == username)

    def get_by_role(self, role: UserRole) -> list[User]:
        return self.find(lambda u: u.role == role)

    def get_active(self) -> list[User]:
        return self.find(lambda u: u.is_active and not u.is_locked)

    def count_by_role(self, role: UserRole) -> int:
        return len(self.get_by_role(role))

    # ------------------------------------------------------------------ 业务
    def is_username_taken(self, username: str, *, exclude_id: str | None = None) -> bool:
        """``True`` 当 username 已存在。可选地排除一个 user id（更新场景）。"""
        return any(user.username == username and user.id != exclude_id for user in self.all())

    def update_points(self, user_id: str, new_balance: int) -> User:
        """原子更新积分余额；找不到抛 :class:`KeyError`。"""
        with self._lock:
            self._ensure_loaded()
            user = self._items.get(user_id)
            if user is None:
                raise KeyError(f"UserRepository.update_points: 用户 {user_id!r} 不存在")
            updated = user.model_copy(update={"points": new_balance})
            updated.touch()
            self._items[user_id] = updated
            self.save()
            return updated


__all__ = ["UserRepository"]
