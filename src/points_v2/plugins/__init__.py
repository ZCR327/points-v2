"""Plugin system（ARCHITECTURE §3 / 隐含在模块依赖方向）。

设计要点
--------

- :class:`Plugin` 抽象基类：所有插件必须实现 :meth:`name` + :meth:`register`
- 加载走 :func:`points_v2.plugins.loader.load_plugins`，使用
  ``importlib.metadata.entry_points(group="points_v2.plugins")``
- 内置插件放在 :mod:`points_v2.plugins.builtin`；可通过 pyproject 注册更多
- 插件不强制使用 UI —— 业务插件可以做"启动时注入额外 service / 注册额外路由"
"""

from __future__ import annotations

from points_v2.plugins.base import Plugin, PluginContext

__all__ = ["Plugin", "PluginContext"]
