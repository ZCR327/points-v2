"""PointsRepository — 积分流水持久化 + 聚合查询。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from points_v2.data.base import JsonRepository
from points_v2.domain.enums import OperationType
from points_v2.domain.points import PointsRecord


class PointsRepository(JsonRepository[PointsRecord]):
    """``data/points.json`` 仓储。"""

    _FILENAME = "points.json"

    def _pk(self, obj: PointsRecord) -> str:
        return obj.id

    # ------------------------------------------------------------------ 查询
    def get_by_user(
        self,
        user_id: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        operation: OperationType | None = None,
        limit: int | None = None,
    ) -> list[PointsRecord]:
        """按用户过滤；可叠加时间范围 / 操作类型 / 数量上限。"""
        with self._lock:
            self._ensure_loaded()
            result: list[PointsRecord] = []
            for rec in self._items.values():
                if rec.user_id != user_id:
                    continue
                if since is not None and rec.created_at < since:
                    continue
                if until is not None and rec.created_at > until:
                    continue
                if operation is not None and rec.operation != operation:
                    continue
                result.append(rec)
        result.sort(key=lambda r: r.created_at, reverse=True)
        if limit is not None and limit >= 0:
            result = result[:limit]
        return result

    def total_earned(self, user_id: str) -> int:
        """用户累计获得的正积分（不区分操作类型，amount 字段恒为正）。"""
        return sum(rec.amount for rec in self.get_by_user(user_id))

    def total_by_operation(self, user_id: str, operation: OperationType) -> int:
        return sum(rec.amount for rec in self.get_by_user(user_id, operation=operation))

    def recent_days(self, user_id: str, days: int) -> list[PointsRecord]:
        """最近 N 天的流水。"""
        if days <= 0:
            return []
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
        return self.get_by_user(user_id, since=cutoff)

    def ranking(self, *, limit: int = 10) -> list[tuple[str, int]]:
        """聚合每个用户的总积分（amount 累加），按降序返回 ``[(user_id, total), ...]``。"""
        with self._lock:
            self._ensure_loaded()
            totals: dict[str, int] = {}
            for rec in self._items.values():
                totals[rec.user_id] = totals.get(rec.user_id, 0) + rec.amount
        ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[: max(0, limit)]


__all__ = ["PointsRepository"]
