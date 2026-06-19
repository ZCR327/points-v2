"""``/api/users`` router — CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from points_v2.api.deps import (
    CurrentUser,
    get_user_service,
    require_role,
)
from points_v2.api.schemas import (
    SuccessResponse,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from points_v2.domain.enums import UserRole
from points_v2.domain.user import User
from points_v2.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])

AdminUser = require_role(UserRole.ADMIN, UserRole.SUPER_ADMIN)


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        points=user.points,
        is_active=user.is_active,
        is_locked=user.is_locked,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
    )


def _to_create_model(payload: UserCreateRequest):
    from points_v2.domain.user import UserCreate

    return UserCreate(
        username=payload.username,
        display_name=payload.display_name,
        password=payload.password,
        role=payload.role,
        initial_points=payload.initial_points,
    )


@router.get("", response_model=list[UserResponse])
async def list_users(
    _current_user: CurrentUser,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    user_service: UserService = Depends(get_user_service),
) -> list[UserResponse]:
    """列出所有用户（任意登录用户可调用——v5.9 同款；生产可加 admin 限制）。"""
    return [_user_to_response(u) for u in user_service.list(offset=offset, limit=limit)]


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    payload: UserCreateRequest,
    _admin: AdminUser,
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    """创建用户（**admin**）。"""
    user = user_service.create(_to_create_model(payload))
    return _user_to_response(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    _current_user: CurrentUser,
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    """根据 id 取用户。"""
    return _user_to_response(user_service.get_by_id(user_id))


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    current_user: CurrentUser,
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    """更新用户。

    - admin 可以改任意用户
    - 普通用户只能改自己（仅允许 display_name）
    """
    from points_v2.domain.user import UserUpdate

    is_self = current_user.id == user_id
    is_admin = current_user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
    if not is_self and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "无权修改其他用户"},
        )
    if (
        is_self
        and not is_admin
        and (
            payload.role is not None
            or payload.is_active is not None
            or payload.is_locked is not None
        )
    ):
        # 普通用户只能改 display_name
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "普通用户不能修改角色/状态"},
        )

    if not payload.has_any():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMPTY_UPDATE", "message": "至少需要更新一个字段"},
        )

    patch = UserUpdate(
        display_name=payload.display_name,
        role=payload.role,
        is_active=payload.is_active,
        is_locked=payload.is_locked,
        points=payload.points,
    )
    return _user_to_response(user_service.update(user_id, patch))


@router.delete("/{user_id}", response_model=SuccessResponse)
async def delete_user(
    user_id: str,
    _admin: AdminUser,
    user_service: UserService = Depends(get_user_service),
) -> SuccessResponse:
    """删除用户（**admin**）。"""
    user_service.delete(user_id)
    return SuccessResponse(message="已删除")


__all__ = ["router"]
