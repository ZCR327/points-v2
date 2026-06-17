"""示范插件（ARCHITECTURE §3 / 演示用）。

设计要点
--------

- 最简单的 :class:`Plugin` 实现：仅打印日志 + 在 :attr:`extras` 注册一个计数器
- 用于验证插件系统正常工作（``load_plugins()`` 至少能跑出一个）
- 真实业务插件可参考此结构：注入 service、注册路由、注入 UI 菜单……
"""

from __future__ import annotations

from datetime import datetime, timezone

from points_v2.plugins.base import Plugin, PluginContext

__all__ = ["ExamplePlugin"]


class ExamplePlugin(Plugin):
    """最小示范插件。"""

    @property
    def name(self) -> str:
        return "example"

    def register(self, ctx: PluginContext) -> None:
        """加载时执行：记日志 + 在 ctx 上挂载 metadata。"""
        ctx.logger.info("ExamplePlugin 已加载 — 演示插件系统工作正常")
        ctx.extras["loaded_at"] = datetime.now(tz=timezone.utc).isoformat()
        ctx.extras["user_repo_count"] = len(ctx.services.user_repo.all())
        ctx.logger.info(
            "ExamplePlugin metadata 已挂载",
            users=ctx.extras["user_repo_count"],
        )
