"""NotificationRepository — 通知持久化 + 范围查询。"""

from __future__ import annotations

from points_v2.data.base import JsonRepository
from points_v2.domain.notification import Notification


class NotificationRepository(JsonRepository[Notification]):
    """``data/notifications.json`` 仓储。"""

    _FILENAME = "notifications.json"

    def _pk(self, obj: Notification) -> str:
        return obj.id

    # ------------------------------------------------------------------ 查询
    def list_for_user(
        self,
        user_id: str | None,
        *,
        include_global: bool = True,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[Notification]:
        """``user_id`` 自己的 + (可选) ``user_id is None`` 的全局通知。"""
        with self._lock:
            self._ensure_loaded()
            results: list[Notification] = []
            for n in self._items.values():
                matches = n.user_id == user_id or (include_global and n.user_id is None)
                if not matches:
                    continue
                if unread_only and n.is_read:
                    continue
                results.append(n)
        results.sort(key=lambda n: n.created_at, reverse=True)
        return results[: max(0, limit)]

    def mark_read(self, notification_id: str) -> bool:
        """标记已读；返回是否真的改了状态。"""
        with self._lock:
            self._ensure_loaded()
            obj = self._items.get(notification_id)
            if obj is None:
                return False
            if obj.is_read:
                return False
            updated = obj.model_copy(update={"is_read": True})
            self._items[notification_id] = updated
            self.save()
            return True

    def global_broadcast(self) -> list[Notification]:
        """所有 ``user_id is None`` 的通知。"""
        return self.find(lambda n: n.user_id is None)


__all__ = ["NotificationRepository"]
