"""NotificationService — 通知创建 / 列出 / 标记已读 / 广播。

设计要点
--------

- ``create`` 支持定向（``user_id``）和全局（``user_id is None``）
- ``broadcast`` 是 create 的语法糖：``user_id=None`` + 自动遍历所有用户
- ``list_for_user`` 合并「自己的」和「全局」通知（取决于 ``include_global``）
- ``mark_read`` 幂等：重复调用不报错、也不重复写盘
- **不直接调其他 service** —— 上层（auth_service 等）负责插入业务通知

依赖
----
- :class:`points_v2.data.notification_repo.NotificationRepository`
- :class:`points_v2.data.user_repo.UserRepository` （用于 broadcast）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from points_v2.core.logging import get_logger
from points_v2.domain.enums import NotificationLevel
from points_v2.domain.notification import Notification

if TYPE_CHECKING:
    from points_v2.data.notification_repo import NotificationRepository
    from points_v2.data.user_repo import UserRepository

__all__ = ["NotificationService"]


class NotificationService:
    """通知服务。"""

    def __init__(
        self,
        notification_repo: NotificationRepository,
        user_repo: UserRepository | None = None,
    ) -> None:
        self._notification_repo = notification_repo
        self._user_repo = user_repo
        self._log = get_logger("system")

    def create(
        self,
        level: NotificationLevel,
        title: str,
        content: str,
        *,
        user_id: str | None = None,
    ) -> Notification:
        """创建一条通知。``user_id=None`` 表示全员。"""
        if not title or not isinstance(title, str):
            raise ValueError("title 必须是非空字符串")
        if not isinstance(content, str):
            raise ValueError("content 必须是字符串")
        if not isinstance(level, NotificationLevel):
            # 允许从字符串构造
            level = NotificationLevel(level)
        n = Notification(
            user_id=user_id,
            level=level,
            title=title.strip(),
            content=content,
        )
        self._notification_repo.insert(n)
        self._log.info(
            "通知创建",
            level=level.value,
            user_id=user_id or "global",
            title=title[:32],
        )
        return n

    def list_for_user(
        self,
        user_id: str,
        *,
        include_global: bool = True,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[Notification]:
        """列出某用户的通知（含全局）。"""
        if limit <= 0 or limit > 500:
            raise ValueError("limit 必须在 1..500 之间")
        return self._notification_repo.list_for_user(
            user_id,
            include_global=include_global,
            unread_only=unread_only,
            limit=limit,
        )

    def mark_read(self, notification_id: str) -> bool:
        """标记已读；幂等。返回是否真的改了状态。"""
        return self._notification_repo.mark_read(notification_id)

    def broadcast(
        self,
        level: NotificationLevel,
        title: str,
        content: str,
    ) -> Notification:
        """广播通知（``user_id=None``）。只创建**一条全局记录**，由 ``list_for_user`` 拼装。

        注：v2 设计为「一条全局记录」而不是「N 条用户记录」（避免 N 倍写入 + 文件膨胀）。
        """
        return self.create(level, title, content, user_id=None)
