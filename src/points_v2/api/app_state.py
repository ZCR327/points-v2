"""App state — shared services bundle.

设计要点
--------

- 把所有默认 service 集中构造，避免在 ``deps.py`` 里散落多处 import + 初始化
- 测试可以 ``app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()``
  或直接 ``container.register(...)`` 替换
- 单进程内：所有 service 共享同一组 repo（同一份内存数据）
- 附带 :class:`QThreadPool`，给 UI 层做后台任务用；API 层不需要
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from PySide6.QtCore import QThreadPool


@dataclass
class ServiceBundle:
    """一组默认构造的 service。

    注：``frozen=False`` 因为 :class:`QThreadPool` 在某些 Qt 版本下不能 pickle，
    且我们需要在测试中能替换。
    """

    user_repo: UserRepository
    points_repo: PointsRepository
    audit_repo: AuditRepository
    notification_repo: NotificationRepository
    auth_service: AuthService
    user_service: UserService
    points_service: PointsService
    audit_service: AuditService
    notification_service: NotificationService
    threadpool: QThreadPool | None = None


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

    # threadpool 延迟到 UI 启动时填充（避免 api/CLI 路径拖入 PySide6）
    threadpool = None
    try:
        from PySide6.QtCore import QThreadPool

        threadpool = QThreadPool.globalInstance()
    except ImportError:  # noqa: BLE001 - PySide6 不在也无所谓
        threadpool = None

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
        threadpool=threadpool,
    )


__all__ = ["ServiceBundle", "build_default_services"]
