"""Plugin 抽象基类（ARCHITECTURE §3 / 隐含在 plugins/）。

设计要点
--------

- :class:`Plugin` 是协议类：子类必须实现 :meth:`name` 和 :meth:`register`
- :class:`PluginContext` 注入给插件：一个"能访问 service / event / logger"的对象
  - 避免插件直接 import 上层（保持依赖方向）
- :meth:`register` **只调一次**：在 :func:`loader.load_plugins` 中
- 插件可以注册 API 路由、注入 UI 菜单、监听事件……
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from loguru import Logger

    from points_v2.api.app_state import ServiceBundle

__all__ = ["Plugin", "PluginContext"]


@dataclass
class PluginContext:
    """插件可访问的上下文。

    :param name: 加载器名（通常是 entry point 的 name）
    :param services: 默认 service bundle（可读、可替换）
    :param logger: 分类 logger（``"plugin"`` 类）
    :param extras: 自由字典，预留给将来扩展（配置 / 事件总线 / 等）
    """

    name: str
    services: ServiceBundle
    logger: Logger
    extras: dict[str, Any] = field(default_factory=dict)


class Plugin(ABC):
    """插件抽象基类。

    实现示例::

        class HelloPlugin(Plugin):
            @property
            def name(self) -> str:
                return "hello"

            def register(self, ctx: PluginContext) -> None:
                ctx.logger.info("Hello from plugin!")
                # ... 业务逻辑（注册 service / 路由 / 监听事件）
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """插件唯一名（用于日志 / 配置定位）。"""

    @abstractmethod
    def register(self, ctx: PluginContext) -> None:
        """加载时调用：注册服务、路由、菜单等。"""
