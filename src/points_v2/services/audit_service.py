"""AuditService — 审计日志写入 / 查询。

设计要点
--------

- ``log`` 接受任意 ``action`` 字符串（除枚举常见动作外，允许业务自定义）
- ``query`` 接受 :class:`AuditFilter` —— Pydantic 已经做了边界检查
- ``get_user_actions`` 是单用户最近 N 天动作的快捷方式
- 审计**只追加、不修改**——所以 repo 用 ``insert``；调用方不应调 ``update``

依赖
----
- :class:`points_v2.data.audit_repo.AuditRepository`
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from points_v2.core.logging import get_logger
from points_v2.domain.audit import AuditFilter, AuditLog

if TYPE_CHECKING:
    from points_v2.data.audit_repo import AuditRepository

__all__ = ["AuditService"]


class AuditService:
    """审计服务：append-only 日志写入 + 灵活查询。"""

    def __init__(self, audit_repo: AuditRepository) -> None:
        self._audit_repo = audit_repo
        self._log = get_logger("system")

    def log(
        self,
        action: str,
        *,
        user_id: str | None = None,
        resource: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        """追加一条审计日志。返回完整 :class:`AuditLog`（含 id / created_at）。"""
        if not action or not isinstance(action, str):
            raise ValueError("action 必须是非空字符串")
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            details=details or {},
            ip_address=ip_address,
        )
        self._audit_repo.insert(entry)
        # 只在 sensitive 类别打日志（避免日志洪水）
        if "sensitive" in action.lower() or "auth" in action.lower():
            self._log.info(
                "审计写入",
                action=action,
                user_id=user_id,
                resource=resource,
            )
        return entry

    def query(self, flt: AuditFilter) -> list[AuditLog]:
        """按 :class:`AuditFilter` 过滤审计。"""
        if not isinstance(flt, AuditFilter):
            raise TypeError(f"query 期望 AuditFilter，got {type(flt).__name__}")
        return self._audit_repo.query(flt)

    def get_user_actions(
        self,
        user_id: str,
        *,
        days: int = 7,
        limit: int = 100,
    ) -> list[AuditLog]:
        """单个用户最近 N 天的动作（倒序）。"""
        if days < 0:
            raise ValueError("days 不能为负")
        if limit <= 0 or limit > 1000:
            raise ValueError("limit 必须在 1..1000 之间")
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
        # 用 AuditFilter 复用 repo 逻辑
        flt = AuditFilter(user_id=user_id, since=cutoff, limit=limit)
        return self._audit_repo.query(flt)
