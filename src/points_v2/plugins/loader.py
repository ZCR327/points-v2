"""插件加载器（entry_points ``group="points_v2.plugins"``）。

设计要点
--------

- :func:`load_plugins` 调用 :func:`importlib.metadata.entry_points` 拿所有
  注册到 ``points_v2.plugins`` 组的 entry point
- 每个 entry point 解析为 :class:`Plugin` 实例，调 :meth:`Plugin.register`
- **不会**重复加载同名插件（去重）
- 加载失败不阻塞启动 —— 写日志后继续
- 三个返回：
  - :func:`load_plugins` → list[PluginContext]（实际加载成功的）
  - :func:`discover_plugins` → list[Plugin]（解析但未 register）
  - :func:`plugin_names` → list[str]（只看名字，不实例化）
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from points_v2.core.logging import get_logger
from points_v2.plugins.base import Plugin, PluginContext

if TYPE_CHECKING:
    from importlib.metadata import EntryPoint

    from points_v2.api.app_state import ServiceBundle

__all__ = [
    "ENTRY_POINT_GROUP",
    "load_plugins",
    "discover_plugins",
    "plugin_names",
]

ENTRY_POINT_GROUP: str = "points_v2.plugins"


def _iter_entry_points() -> Iterable[EntryPoint]:
    """跨 Python 版本的 entry_points 解析。"""
    eps = __import__("importlib.metadata").metadata.entry_points
    # Python 3.10+ 的 entry_points() 返回 SelectableGroups / EntryPoints
    try:
        return list(eps(group=ENTRY_POINT_GROUP))
    except TypeError:
        # 旧式 dict 风格
        try:
            groups = eps()
        except TypeError:  # pragma: no cover
            return []
        return list(groups.get(ENTRY_POINT_GROUP, []))


def plugin_names() -> list[str]:
    """返回所有已注册插件名（不实例化）。"""
    return [ep.name for ep in _iter_entry_points()]


def discover_plugins() -> list[Plugin]:
    """解析所有 entry point 为 :class:`Plugin` 实例，**不调 register**。"""
    plugins: list[Plugin] = []
    for ep in _iter_entry_points():
        try:
            obj: Any = ep.load()
        except Exception as exc:  # noqa: BLE001 - 插件失败要 continue
            get_logger("plugin").warning(
                "插件解析失败",
                name=ep.name,
                error=str(exc),
            )
            continue
        if not isinstance(obj, Plugin):
            # 允许 entry point 直接给个类（无参构造）
            try:
                instance = obj()
            except Exception as exc:  # noqa: BLE001
                get_logger("plugin").warning(
                    "插件实例化失败",
                    name=ep.name,
                    error=str(exc),
                )
                continue
            if not isinstance(instance, Plugin):
                get_logger("plugin").warning(
                    "插件类型不匹配",
                    name=ep.name,
                    type=type(instance).__name__,
                )
                continue
            obj = instance
        plugins.append(obj)
    return plugins


def load_plugins(services: ServiceBundle | None = None) -> list[PluginContext]:
    """加载并注册所有插件，返回每个插件的 :class:`PluginContext`。

    :param services: 默认 service bundle；``None`` 时构造新一份（仅含 repo，无 service）。
    :returns: 成功注册的插件上下文列表（去重后）。
    """
    log = get_logger("plugin")
    if services is None:
        # 不依赖 api.app_state（避免循环）；直接构造最小 bundle
        from points_v2.data import (
            AuditRepository,
            NotificationRepository,
            PointsRepository,
            UserRepository,
        )

        services = _MinimalBundle(  # type: ignore[arg-type]
            user_repo=UserRepository(),
            points_repo=PointsRepository(),
            audit_repo=AuditRepository(),
            notification_repo=NotificationRepository(),
        )

    contexts: list[PluginContext] = []
    seen: set[str] = set()
    for plugin in discover_plugins():
        if plugin.name in seen:
            log.warning("插件重名，跳过", name=plugin.name)
            continue
        seen.add(plugin.name)
        ctx = PluginContext(
            name=plugin.name,
            services=services,  # type: ignore[arg-type]
            logger=log,
        )
        try:
            plugin.register(ctx)
        except Exception as exc:  # noqa: BLE001 - 插件失败不阻塞
            log.error(
                "插件 register 失败",
                name=plugin.name,
                error=str(exc),
            )
            continue
        contexts.append(ctx)
        log.info("插件加载完成", name=plugin.name)
    return contexts


# ---------------------------------------------------------------------------
# 最小 bundle（plugins 不依赖 service 层时使用）
# ---------------------------------------------------------------------------
class _MinimalBundle:
    """最小可用的 bundle（只暴露 repo），避开循环 import。"""

    def __init__(
        self,
        *,
        user_repo: Any,
        points_repo: Any,
        audit_repo: Any,
        notification_repo: Any,
    ) -> None:
        self.user_repo = user_repo
        self.points_repo = points_repo
        self.audit_repo = audit_repo
        self.notification_repo = notification_repo
