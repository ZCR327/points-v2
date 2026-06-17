"""PointsService — 积分增减 / 转账 / 历史 / 排行 / 统计。

设计要点
--------

- **加 / 扣 / 转** 都先校验目标用户存在 + 积分合法（``utils.validators.validate_amount``）
- **扣减 / 转账** 校验余额；不足抛 :class:`InsufficientPointsError`（带 ``balance`` / ``required`` 详情）
- **转账** 是一条 ``TRANSFER_OUT`` + 一条 ``TRANSFER_IN``，余额自动双向调整
- 余额通过 :meth:`UserRepository.update_points` 原子更新（一次性 model_copy，不存在 race）
- 排行榜聚合走 :meth:`PointsRepository.ranking`；按 period 过滤
- 统计信息聚合用户数 / 总积分 / 流水数

依赖
----
- :class:`points_v2.data.user_repo.UserRepository`
- :class:`points_v2.data.points_repo.PointsRepository`
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from points_v2.core.exceptions import (
    InsufficientPointsError,
    UserNotFoundError,
)
from points_v2.core.logging import get_logger
from points_v2.domain.enums import OperationType
from points_v2.domain.points import (
    MAX_AMOUNT,
    PointsAdjustment,
    PointsRecord,
    UserRanking,
)
from points_v2.domain.user import User
from points_v2.utils.time import utcnow
from points_v2.utils.validators import validate_amount

if TYPE_CHECKING:
    from points_v2.data.points_repo import PointsRepository
    from points_v2.data.user_repo import UserRepository

__all__ = ["PointsService", "SystemStats"]


# ---------------------------------------------------------------------------
# 聚合类型（API / UI 共用）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SystemStats:
    """系统统计（ARCHITECTURE §7 PointsService.get_stats）。"""

    user_count: int
    total_points: int
    record_count: int
    max_balance: int
    min_balance: int


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class PointsService:
    """积分服务。"""

    def __init__(
        self,
        user_repo: UserRepository,
        points_repo: PointsRepository,
    ) -> None:
        self._user_repo = user_repo
        self._points_repo = points_repo
        self._log = get_logger("points")

    # ------------------------------------------------------------------ 写操作
    def add(
        self,
        user_id: str,
        amount: int,
        reason: str = "",
        operator_id: str | None = None,
    ) -> PointsRecord:
        """加积分（amount 必须正）。返回流水。"""
        amount = validate_amount(amount)
        user = self._get_user(user_id)
        new_balance = self._safe_add(user.points, amount)
        updated = self._user_repo.update_points(user_id, new_balance)
        record = PointsRecord(
            user_id=user_id,
            operation=OperationType.EARN,
            amount=amount,
            balance_after=updated.points,
            reason=reason.strip(),
            operator_id=operator_id,
        )
        self._points_repo.insert(record)
        self._log.info(
            "加积分",
            user_id=user_id,
            amount=amount,
            balance=updated.points,
            operator=operator_id or "system",
        )
        return record

    def deduct(
        self,
        user_id: str,
        amount: int,
        reason: str = "",
        operator_id: str | None = None,
    ) -> PointsRecord:
        """扣积分。失败抛 :class:`InsufficientPointsError`。"""
        amount = validate_amount(amount)
        user = self._get_user(user_id)
        if user.points < amount:
            raise InsufficientPointsError(
                "积分不足",
                balance=user.points,
                required=amount,
            )
        new_balance = user.points - amount
        updated = self._user_repo.update_points(user_id, new_balance)
        record = PointsRecord(
            user_id=user_id,
            operation=OperationType.SPEND,
            amount=amount,
            balance_after=updated.points,
            reason=reason.strip(),
            operator_id=operator_id,
        )
        self._points_repo.insert(record)
        self._log.info(
            "扣积分",
            user_id=user_id,
            amount=amount,
            balance=updated.points,
            operator=operator_id or "system",
        )
        return record

    def transfer(
        self,
        from_id: str,
        to_id: str,
        amount: int,
        reason: str = "",
        operator_id: str | None = None,
    ) -> tuple[PointsRecord, PointsRecord]:
        """转账 from_id → to_id。

        失败条件：
        - from_id == to_id（自己转自己）
        - 任意一方不存在
        - 转账方余额不足

        成功：插入两条流水（TRANSFER_OUT + TRANSFER_IN），余额分别更新。
        """
        amount = validate_amount(amount)
        if from_id == to_id:
            raise ValueError("转账双方不能相同")
        from_user = self._get_user(from_id)
        to_user = self._get_user(to_id)
        if from_user.points < amount:
            raise InsufficientPointsError(
                "积分不足，无法转账",
                balance=from_user.points,
                required=amount,
            )
        now = utcnow()
        new_from = from_user.points - amount
        new_to = self._safe_add(to_user.points, amount)

        # 先扣再加（顺序避免「先把对方加满再扣不到」）；失败时一方也不会被改
        self._user_repo.update_points(from_id, new_from)
        try:
            self._user_repo.update_points(to_id, new_to)
        except Exception:
            # 回滚（用户层补回 from）—— 学生项目够用；生产需事务
            self._user_repo.update_points(from_id, from_user.points)
            raise

        out_record = PointsRecord(
            user_id=from_id,
            operation=OperationType.TRANSFER_OUT,
            amount=amount,
            balance_after=new_from,
            reason=reason.strip(),
            operator_id=operator_id,
            created_at=now,
        )
        in_record = PointsRecord(
            user_id=to_id,
            operation=OperationType.TRANSFER_IN,
            amount=amount,
            balance_after=new_to,
            reason=reason.strip(),
            operator_id=operator_id,
            created_at=now,
        )
        self._points_repo.insert(out_record)
        self._points_repo.insert(in_record)
        self._log.info(
            "转账",
            from_id=from_id,
            to_id=to_id,
            amount=amount,
            operator=operator_id or "system",
        )
        return out_record, in_record

    # ------------------------------------------------------------------ 读操作
    def get_history(
        self,
        user_id: str,
        *,
        days: int = 30,
        limit: int = 100,
    ) -> list[PointsRecord]:
        """取用户积分历史；按时间倒序。

        :param days: 只返回最近 N 天内的；``None`` 表示全部。
        :param limit: 最大条数。
        """
        self._get_user(user_id)  # 不存在直接抛
        if days is None:
            return self._points_repo.get_by_user(user_id, limit=limit)
        if days < 0:
            raise ValueError("days 不能为负")
        return self._points_repo.recent_days(user_id, days)[:limit]

    def get_ranking(
        self,
        *,
        period: Literal["week", "month", "all"] = "all",
        limit: int = 10,
    ) -> list[UserRanking]:
        """排行榜；按 period 过滤后聚合 ``amount``。

        注：``PointsRecord.amount`` 恒正；聚合即「累计获得积分」。
        """
        if limit <= 0 or limit > 100:
            raise ValueError("limit 必须在 1..100 之间")
        if period not in ("week", "month", "all"):
            raise ValueError(f"period 必须是 week/month/all，got {period!r}")
        if period == "all":
            ranked = self._points_repo.ranking(limit=limit)
        else:
            days = 7 if period == "week" else 30
            ranked = self._aggregate_period(days=days, limit=limit)
        # 关联用户名
        result: list[UserRanking] = []
        for rank_idx, (user_id, total) in enumerate(ranked, start=1):
            user = self._user_repo.get(user_id)
            if user is None:
                continue
            result.append(
                UserRanking(
                    rank=rank_idx,
                    user_id=user.id,
                    username=user.username,
                    display_name=user.display_name,
                    total_points=total,
                    period=period,
                ),
            )
        return result

    def get_stats(self) -> SystemStats:
        """系统统计：用户数 / 总积分 / 流水数 / 最大 / 最小余额。"""
        users = self._user_repo.all()
        records = self._points_repo.all()
        user_count = len(users)
        total_points = sum(u.points for u in users)
        record_count = len(records)
        balances = [u.points for u in users]
        max_balance = max(balances) if balances else 0
        min_balance = min(balances) if balances else 0
        return SystemStats(
            user_count=user_count,
            total_points=total_points,
            record_count=record_count,
            max_balance=max_balance,
            min_balance=min_balance,
        )

    # ------------------------------------------------------------------ 兼容
    def apply_adjustment(self, adj: PointsAdjustment) -> PointsRecord:
        """接收 :class:`PointsAdjustment` 输入（统一 service 入口）。"""
        return self.add(
            adj.user_id,
            adj.amount,
            reason=adj.reason,
            operator_id=adj.operator_id,
        )

    # ------------------------------------------------------------------ 内部
    def _get_user(self, user_id: str) -> User:
        user = self._user_repo.get(user_id)
        if user is None:
            raise UserNotFoundError(f"用户 {user_id} 不存在")
        return user

    @staticmethod
    def _safe_add(current: int, amount: int) -> int:
        """加法并防溢出（amount 已 validate ≤ MAX_AMOUNT）。"""
        result = current + amount
        if result > MAX_AMOUNT:
            raise ValueError(
                f"积分累加后超过上限 {MAX_AMOUNT}",
                # 注：base PointsV2Error 不接 details；保持 ValueError
            )
        return result

    def _aggregate_period(self, *, days: int, limit: int) -> list[tuple[str, int]]:
        """按周期聚合每个用户的 amount 累加。"""
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
        totals: dict[str, int] = {}
        with self._points_repo._lock:  # type: ignore[attr-defined]  # 内部一致
            self._points_repo._ensure_loaded()  # type: ignore[attr-defined]
            for rec in self._points_repo._items.values():  # type: ignore[attr-defined]
                if rec.created_at >= cutoff:
                    totals[rec.user_id] = totals.get(rec.user_id, 0) + rec.amount
        ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:limit]
