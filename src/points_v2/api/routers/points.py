"""``/api/points`` router — 积分查询 / 加减 / 转账."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from points_v2.api.deps import (
    CurrentUser,
    get_points_service,
    get_user_service,
)
from points_v2.api.schemas import (
    PointsAddRequest,
    PointsBalanceResponse,
    PointsDeductRequest,
    PointsHistoryResponse,
    PointsRecordResponse,
    PointsTransferRequest,
)
from points_v2.domain.enums import UserRole
from points_v2.domain.points import PointsRecord
from points_v2.services.points_service import PointsService
from points_v2.services.user_service import UserService

router = APIRouter(tags=["points"])


def _record_to_response(record: PointsRecord) -> PointsRecordResponse:
    return PointsRecordResponse(
        id=record.id,
        user_id=record.user_id,
        operation=record.operation,
        amount=record.amount,
        balance_after=record.balance_after,
        reason=record.reason,
        operator_id=record.operator_id,
        created_at=record.created_at,
    )


# ---------------------------------------------------------------------------
# 嵌套在 users 下的查询路由
# ---------------------------------------------------------------------------
users_router = APIRouter(prefix="/users", tags=["points"])


@users_router.get("/{user_id}/points", response_model=PointsBalanceResponse)
async def get_user_points(
    user_id: str,
    _current_user: CurrentUser,
    user_service: UserService = Depends(get_user_service),
) -> PointsBalanceResponse:
    """查某用户积分余额。"""
    user = user_service.get_by_id(user_id)
    return PointsBalanceResponse(user_id=user.id, username=user.username, points=user.points)


@users_router.get("/{user_id}/points/history", response_model=PointsHistoryResponse)
async def get_user_points_history(
    user_id: str,
    _current_user: CurrentUser,
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=100, ge=1, le=500),
    points_service: PointsService = Depends(get_points_service),
) -> PointsHistoryResponse:
    """查某用户积分历史。"""
    records = points_service.get_history(user_id, days=days, limit=limit)
    return PointsHistoryResponse(
        user_id=user_id,
        total=len(records),
        records=[_record_to_response(r) for r in records],
    )


# 顶层 /api/points/* 写操作
@router.post("/points/add", response_model=PointsRecordResponse)
async def add_points(
    payload: PointsAddRequest,
    current_user: CurrentUser,
    points_service: PointsService = Depends(get_points_service),
) -> PointsRecordResponse:
    """加积分（**admin / operator**）。"""
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.OPERATOR):
        from fastapi import HTTPException
        from fastapi import status as _st

        raise HTTPException(
            status_code=_st.HTTP_403_FORBIDDEN,
            detail={"code": "INSUFFICIENT_ROLE", "message": "需要 admin / operator 权限"},
        )
    record = points_service.add(
        payload.user_id,
        payload.amount,
        reason=payload.reason,
        operator_id=current_user.id,
    )
    return _record_to_response(record)


@router.post("/points/deduct", response_model=PointsRecordResponse)
async def deduct_points(
    payload: PointsDeductRequest,
    current_user: CurrentUser,
    points_service: PointsService = Depends(get_points_service),
) -> PointsRecordResponse:
    """扣积分（**admin / operator**）。"""
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.OPERATOR):
        from fastapi import HTTPException
        from fastapi import status as _st

        raise HTTPException(
            status_code=_st.HTTP_403_FORBIDDEN,
            detail={"code": "INSUFFICIENT_ROLE", "message": "需要 admin / operator 权限"},
        )
    record = points_service.deduct(
        payload.user_id,
        payload.amount,
        reason=payload.reason,
        operator_id=current_user.id,
    )
    return _record_to_response(record)


@router.post("/points/transfer", response_model=PointsHistoryResponse)
async def transfer_points(
    payload: PointsTransferRequest,
    current_user: CurrentUser,
    points_service: PointsService = Depends(get_points_service),
) -> PointsHistoryResponse:
    """转账（**登录用户**均可：自己发起转给别人；admin 可代转）。"""
    out, inc = points_service.transfer(
        payload.from_user_id,
        payload.to_user_id,
        payload.amount,
        reason=payload.reason,
        operator_id=current_user.id,
    )
    return PointsHistoryResponse(
        user_id=payload.from_user_id,
        total=2,
        records=[_record_to_response(out), _record_to_response(inc)],
    )


# 把嵌套路由挂到 router
router.include_router(users_router)


__all__ = ["router"]
