"""FastAPI dependencies: get_current_user, require_role, service singletons.

设计要点
--------

- 服务通过 :class:`points_v2.core.container.Container` 解析（**首次访问才构造**）
  → 单元测试可 ``container.register("auth_service", lambda: FakeAuthService())`` 注入
- ``get_current_user`` 解析 ``Authorization: Bearer <token>``，调 ``AuthService.verify_token``
- ``require_role(role)`` 返回一个 dependency；不满足抛 403
- 失败统一抛 :class:`points_v2.core.exceptions.PointsV2Error` 及其子类
  → 在 ``app.py`` 集中转 JSON 响应
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from points_v2.core.container import container
from points_v2.core.exceptions import (
    AuthError,
    InvalidCredentialsError,
    PointsV2Error,
)
from points_v2.domain.enums import UserRole
from points_v2.domain.user import User
from points_v2.services import (
    AuditService,
    AuthService,
    NotificationService,
    PointsService,
    UserService,
)


# ---------------------------------------------------------------------------
# 服务解析（容器优先；未注册时构造默认实例）
# ---------------------------------------------------------------------------
def get_auth_service() -> AuthService:
    if container.has("auth_service"):
        return container.resolve("auth_service")
    # 默认实例化路径（不注册到容器，避免污染）
    from points_v2.api.app_state import build_default_services

    return build_default_services().auth_service


def get_user_service() -> UserService:
    if container.has("user_service"):
        return container.resolve("user_service")
    from points_v2.api.app_state import build_default_services

    return build_default_services().user_service


def get_points_service() -> PointsService:
    if container.has("points_service"):
        return container.resolve("points_service")
    from points_v2.api.app_state import build_default_services

    return build_default_services().points_service


def get_audit_service() -> AuditService:
    if container.has("audit_service"):
        return container.resolve("audit_service")
    from points_v2.api.app_state import build_default_services

    return build_default_services().audit_service


def get_notification_service() -> NotificationService:
    if container.has("notification_service"):
        return container.resolve("notification_service")
    from points_v2.api.app_state import build_default_services

    return build_default_services().notification_service


# ---------------------------------------------------------------------------
# Auth 依赖
# ---------------------------------------------------------------------------
def _extract_bearer_token(authorization: str | None) -> str:
    """从 ``Authorization: Bearer xxx`` 取 token。失败抛 :class:`InvalidCredentialsError`。"""
    if not authorization:
        raise InvalidCredentialsError("缺少 Authorization 头")
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise InvalidCredentialsError("Authorization 头格式错误（应为 Bearer xxx）")
    token = parts[1].strip()
    if not token:
        raise InvalidCredentialsError("Authorization 头为空")
    return token


def get_current_user(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """从 ``Authorization`` 头解析 token，返回对应 :class:`User`."""
    token = _extract_bearer_token(authorization)
    try:
        return auth_service.verify_token(token)
    except InvalidCredentialsError as exc:
        # 401 Unauthorized
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": exc.message},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": exc.message},
        ) from exc


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*allowed: UserRole) -> type[User]:
    """返回一个 ``Annotated[User, Depends(...)]`` 类型别名。

    用法::

        def handler(
            user: require_role(UserRole.ADMIN),  # type: ignore[valid-type]
            ...
        ): ...

    注意：FastAPI 在 0.95+ 支持把 ``Annotated[Type, Depends(...)]`` 直接作为参数注解；
    这里返回 ``Annotated[User, Depends(_checker)]`` 让路由直接用作类型。
    """
    allowed_set = set(allowed)

    def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "INSUFFICIENT_ROLE",
                    "message": "权限不足",
                    "details": {"allowed": [r.value for r in allowed_set]},
                },
            )
        return user

    return Annotated[User, Depends(_checker)]  # type: ignore[return-value]  # noqa: F722


# ---------------------------------------------------------------------------
# 公共：错误转 HTTPException（针对路由直接调 service 的情况）
# ---------------------------------------------------------------------------
def points_v2_error_to_http(exc: PointsV2Error) -> HTTPException:
    """把业务异常映射到 HTTP 状态码（兜底；主要在 exception handler 里处理）。"""
    from points_v2.core.exceptions import (
        DuplicateUserError,
        InsufficientPointsError,
        InvalidCredentialsError,
        UserNotFoundError,
    )

    if isinstance(exc, InvalidCredentialsError):
        code = "INVALID_CREDENTIALS"
        status_code = status.HTTP_401_UNAUTHORIZED
    elif isinstance(exc, InsufficientPointsError):
        code = "INSUFFICIENT_POINTS"
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(exc, UserNotFoundError):
        code = "USER_NOT_FOUND"
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, DuplicateUserError):
        code = "DUPLICATE_USER"
        status_code = status.HTTP_409_CONFLICT
    else:
        code = "POINTS_V2_ERROR"
        status_code = status.HTTP_400_BAD_REQUEST
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": exc.message, "details": exc.details},
    )


def error_response_payload(exc: PointsV2Error) -> dict[str, dict[str, object]]:
    """统一错误响应 dict（用于自定义 exception handler）。"""
    from points_v2.core.exceptions import (
        DuplicateUserError,
        InsufficientPointsError,
        InvalidCredentialsError,
        UserNotFoundError,
    )

    if isinstance(exc, InvalidCredentialsError):
        code = "INVALID_CREDENTIALS"
    elif isinstance(exc, InsufficientPointsError):
        code = "INSUFFICIENT_POINTS"
    elif isinstance(exc, UserNotFoundError):
        code = "USER_NOT_FOUND"
    elif isinstance(exc, DuplicateUserError):
        code = "DUPLICATE_USER"
    else:
        code = "POINTS_V2_ERROR"
    return {
        "error": {
            "code": code,
            "message": exc.message,
            "details": exc.details,
        },
    }


def status_for_error(exc: PointsV2Error) -> int:
    """错误对应的 HTTP 状态码（与 :func:`error_response_payload` 保持一致）。"""
    from points_v2.core.exceptions import (
        DuplicateUserError,
        InsufficientPointsError,
        InvalidCredentialsError,
        UserNotFoundError,
    )

    if isinstance(exc, InvalidCredentialsError):
        return status.HTTP_401_UNAUTHORIZED
    if isinstance(exc, InsufficientPointsError):
        return status.HTTP_409_CONFLICT
    if isinstance(exc, UserNotFoundError):
        return status.HTTP_404_NOT_FOUND
    if isinstance(exc, DuplicateUserError):
        return status.HTTP_409_CONFLICT
    return status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
def liveness_probe() -> Iterator[tuple[str, str]]:
    """轻量级依赖检查（``/health`` 用）。"""
    yield ("status", "ok")


__all__ = [
    "get_auth_service",
    "get_user_service",
    "get_points_service",
    "get_audit_service",
    "get_notification_service",
    "get_current_user",
    "CurrentUser",
    "require_role",
    "points_v2_error_to_http",
    "error_response_payload",
    "status_for_error",
    "liveness_probe",
]
