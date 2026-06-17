"""``/api/auth`` router — login / logout / me."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from points_v2.api.deps import CurrentUser, get_auth_service
from points_v2.api.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    SuccessResponse,
    UserInfoResponse,
)
from points_v2.domain.user import User
from points_v2.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_to_info(user: User) -> UserInfoResponse:
    return UserInfoResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        points=user.points,
        is_active=user.is_active,
        is_locked=user.is_locked,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    """登录拿 token（无 Authorization 头）。"""
    token = auth_service.login(
        payload.username,
        payload.password,
        ip_address=None,  # FastAPI 反向代理后才易拿到真实 IP；此处先 None
    )
    return LoginResponse(
        token=token.token,
        expires_at=token.expires_at,
        user_id=token.user_id,
        username=token.username,
        role=token.role,
    )


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    auth_service: AuthService = Depends(get_auth_service),
) -> SuccessResponse:
    """登出：删除当前 token。"""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MISSING_TOKEN", "message": "缺少 Authorization 头"},
        )
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_AUTH_FORMAT", "message": "Authorization 格式错误"},
        )
    auth_service.logout(parts[1].strip())
    return SuccessResponse(message="已登出")


@router.get("/me", response_model=UserInfoResponse)
async def me(current_user: CurrentUser) -> UserInfoResponse:
    """当前登录用户信息。"""
    return _user_to_info(current_user)


@router.post("/change-password", response_model=SuccessResponse)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUser,
    auth_service: AuthService = Depends(get_auth_service),
) -> SuccessResponse:
    """改密（需登录 + 旧密码）。"""
    auth_service.change_password(
        current_user.id,
        payload.old_password,
        payload.new_password,
    )
    return SuccessResponse(message="密码已修改")


__all__ = ["router"]
