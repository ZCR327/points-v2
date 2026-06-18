"""FastAPI HTTP API."""

from __future__ import annotations

from points_v2.api.app import create_app, main
from points_v2.api.app_state import ServiceBundle, build_default_services
from points_v2.api.schemas import (
    AuditListResponse,
    AuditLogResponse,
    ChangePasswordRequest,
    ErrorResponse,
    LoginRequest,
    LoginResponse,
    NotificationCreateRequest,
    NotificationListResponse,
    NotificationResponse,
    PointsAddRequest,
    PointsBalanceResponse,
    PointsHistoryResponse,
    PointsRecordResponse,
    PointsTransferRequest,
    RankingItemResponse,
    RankingResponse,
    SuccessResponse,
    SystemStatsResponse,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)

__all__ = [
    "create_app",
    "main",
    "ServiceBundle",
    "build_default_services",
    "LoginRequest",
    "LoginResponse",
    "UserCreateRequest",
    "UserResponse",
    "UserUpdateRequest",
    "PointsAddRequest",
    "PointsBalanceResponse",
    "PointsHistoryResponse",
    "PointsRecordResponse",
    "PointsTransferRequest",
    "RankingItemResponse",
    "RankingResponse",
    "SystemStatsResponse",
    "AuditListResponse",
    "AuditLogResponse",
    "NotificationCreateRequest",
    "NotificationListResponse",
    "NotificationResponse",
    "ChangePasswordRequest",
    "SuccessResponse",
    "ErrorResponse",
]
