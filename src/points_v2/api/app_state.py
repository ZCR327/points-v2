"""App state — shared services bundle.

设计要点
--------

- 把所有默认 service 集中构造，避免在 ``deps.py`` 里散落多处 import + 初始化
- 测试可以 ``app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()``
  或直接 ``container.register(...)`` 替换
- 单进程内：所有 service 共享同一组 repo（同一份内存数据）
"""

from __future__ import annotations

from dataclasses import dataclass

from points_v2.data import (
    AuditRepository,
    NotificationRepository,
    PointsRepository,
    UserRepository,
)
from points_v2.services import (
    AuditService,
    AuthService,
    NotificationService,
    PointsService,
    UserService,
)


@dataclass(frozen=True)
class ServiceBundle:
    """一组默认构造的 service。"""

    user_repo: UserRepository
    points_repo: PointsRepository
    audit_repo: AuditRepository
    notification_repo: NotificationRepository
    auth_service: AuthService
    user_service: UserService
    points_service: PointsService
    audit_service: AuditService
    notification_service: NotificationService


def build_default_services() -> ServiceBundle:
    """构造默认 service 集合（**不**注册到 container，调用方按需注册）。"""
    user_repo = UserRepository()
    points_repo = PointsRepository()
    audit_repo = AuditRepository()
    notification_repo = NotificationRepository()

    auth_service = AuthService(user_repo=user_repo, audit_repo=audit_repo)
    user_service = UserService(user_repo=user_repo)
    points_service = PointsService(user_repo=user_repo, points_repo=points_repo)
    audit_service = AuditService(audit_repo=audit_repo)
    notification_service = NotificationService(
        notification_repo=notification_repo,
        user_repo=user_repo,
    )

    return ServiceBundle(
        user_repo=user_repo,
        points_repo=points_repo,
        audit_repo=audit_repo,
        notification_repo=notification_repo,
        auth_service=auth_service,
        user_service=user_service,
        points_service=points_service,
        audit_service=audit_service,
        notification_service=notification_service,
    )


__all__ = ["ServiceBundle", "build_default_services"]
