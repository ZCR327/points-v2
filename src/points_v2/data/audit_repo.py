"""AuditRepository — 审计日志（按时间倒序追加）。"""

from __future__ import annotations

from points_v2.data.base import JsonRepository
from points_v2.domain.audit import AuditFilter, AuditLog


class AuditRepository(JsonRepository[AuditLog]):
    """``data/audit.json`` 仓储。"""

    _FILENAME = "audit.json"

    def _pk(self, obj: AuditLog) -> str:
        return obj.id

    # ------------------------------------------------------------------ 查询
    def query(self, flt: AuditFilter) -> list[AuditLog]:
        """按 :class:`AuditFilter` 过滤 + 倒序 + 分页。"""
        with self._lock:
            self._ensure_loaded()
            action_str = flt.action_str
            results: list[AuditLog] = []
            for log in self._items.values():
                if flt.user_id is not None and log.user_id != flt.user_id:
                    continue
                if action_str is not None and log.action_str != action_str:
                    continue
                if flt.resource is not None and log.resource != flt.resource:
                    continue
                if flt.since is not None and log.created_at < flt.since:
                    continue
                if flt.until is not None and log.created_at > flt.until:
                    continue
                results.append(log)
        results.sort(key=lambda r: r.created_at, reverse=True)
        start = min(flt.offset, len(results))
        end = min(start + flt.limit, len(results))
        return results[start:end]

    def get_by_user(self, user_id: str, *, limit: int = 100) -> list[AuditLog]:
        """单个用户的最近动作（倒序）。"""
        with self._lock:
            self._ensure_loaded()
            results = [log for log in self._items.values() if log.user_id == user_id]
        results.sort(key=lambda r: r.created_at, reverse=True)
        return results[: max(0, limit)]


__all__ = ["AuditRepository"]
