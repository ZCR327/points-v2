"""``/api/admin`` router — rankings / stats / audit / notifications."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from points_v2.api.deps import (
    CurrentUser,
    get_audit_service,
    get_notification_service,
    get_points_service,
    require_role,
)
from points_v2.api.schemas import (
    AuditListResponse,
    AuditLogResponse,
    NotificationCreateRequest,
    NotificationListResponse,
    NotificationResponse,
    RankingResponse,
    RankingItemResponse,
    SuccessResponse,
    SystemStatsResponse,
)
from points_v2.domain.audit import AuditFilter
from points_v2.domain.enums import UserRole
from points_v2.services.audit_service import AuditService
from points_v2.services.notification_service import NotificationService
from points_v2.services.points_service import PointsService

router = APIRouter(prefix="/admin", tags=["admin"])

# 类型别名：admin / super_admin
AdminUser = require_role(UserRole.ADMIN, UserRole.SUPER_ADMIN)


# ---------------------------------------------------------------------------
# Rankings & Stats（**admin**）
# ---------------------------------------------------------------------------
@router.get("/rankings", response_model=RankingResponse)
async def get_rankings(
    _admin: AdminUser,
    period: Annotated[Literal["week", "month", "all"], Query()] = "all",
    limit: int = Query(default=10, ge=1, le=100),
    points_service: PointsService = Depends(get_points_service),
) -> RankingResponse:
    """排行榜。"""
    rows = points_service.get_ranking(period=period, limit=limit)
    return RankingResponse(
        period=period,
        items=[
            RankingItemResponse(
                rank=row.rank,
                user_id=row.user_id,
                username=row.username,
                display_name=row.display_name,
                total_points=row.total_points,
                period=row.period,
            )
            for row in rows
        ],
    )


@router.get("/stats", response_model=SystemStatsResponse)
async def get_stats(
    _admin: AdminUser,
    points_service: PointsService = Depends(get_points_service),
) -> SystemStatsResponse:
    """系统统计。"""
    stats = points_service.get_stats()
    return SystemStatsResponse(
        user_count=stats.user_count,
        total_points=stats.total_points,
        record_count=stats.record_count,
        max_balance=stats.max_balance,
        min_balance=stats.min_balance,
    )


# ---------------------------------------------------------------------------
# Audit（**admin**）
# ---------------------------------------------------------------------------
@router.get("/audit", response_model=AuditListResponse)
async def query_audit(
    _admin: AdminUser,
    user_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    resource: str | None = Query(default=None),
    since: str | None = Query(default=None),
    until: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    audit_service: AuditService = Depends(get_audit_service),
) -> AuditListResponse:
    """审计查询。"""
    from points_v2.utils.time import parse_datetime

    flt = AuditFilter(
        user_id=user_id,
        action=action,
        resource=resource,
        since=parse_datetime(since) if since else None,
        until=parse_datetime(until) if until else None,
        offset=offset,
        limit=limit,
    )
    rows = audit_service.query(flt)
    return AuditListResponse(
        total=len(rows),
        items=[
            AuditLogResponse(
                id=log.id,
                user_id=log.user_id,
                action=log.action_str,
                resource=log.resource,
                details=log.details,
                ip_address=log.ip_address,
                created_at=log.created_at,
            )
            for log in rows
        ],
    )


# ---------------------------------------------------------------------------
# Notifications（任意登录用户可看自己的；admin 可广播）
# ---------------------------------------------------------------------------
@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    current_user: CurrentUser,
    include_global: bool = Query(default=True),
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=500),
    notification_service: NotificationService = Depends(get_notification_service),
) -> NotificationListResponse:
    """列出当前用户通知（含全局）。"""
    rows = notification_service.list_for_user(
        current_user.id,
        include_global=include_global,
        unread_only=unread_only,
        limit=limit,
    )
    return NotificationListResponse(
        total=len(rows),
        items=[
            NotificationResponse(
                id=n.id,
                user_id=n.user_id,
                level=n.level,
                title=n.title,
                content=n.content,
                is_read=n.is_read,
                created_at=n.created_at,
            )
            for n in rows
        ],
    )


@router.post("/notifications", response_model=NotificationResponse)
async def create_notification(
    payload: NotificationCreateRequest,
    _admin: AdminUser,
    notification_service: NotificationService = Depends(get_notification_service),
) -> NotificationResponse:
    """创建通知（**admin**；``user_id=None`` 表示广播）。"""
    n = notification_service.create(
        payload.level,
        payload.title,
        payload.content,
        user_id=payload.user_id,
    )
    return NotificationResponse(
        id=n.id,
        user_id=n.user_id,
        level=n.level,
        title=n.title,
        content=n.content,
        is_read=n.is_read,
        created_at=n.created_at,
    )


@router.post("/notifications/{notification_id}/read", response_model=SuccessResponse)
async def mark_notification_read(
    notification_id: str,
    current_user: CurrentUser,
    notification_service: NotificationService = Depends(get_notification_service),
) -> SuccessResponse:
    """标记通知已读。

    - 普通用户只能标记自己的
    - admin 可标记任意
    """
    # 校验权限：先查一次
    rows = notification_service.list_for_user(current_user.id, include_global=True, limit=500)
    if not any(n.id == notification_id for n in rows) and current_user.role not in (
        UserRole.ADMIN,
        UserRole.SUPER_ADMIN,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "无权标记该通知"},
        )
    notification_service.mark_read(notification_id)
    return SuccessResponse(message="已标记为已读")


__all__ = ["router"]
