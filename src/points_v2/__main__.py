"""Entry point for ``python -m points_v2``.

启动顺序：
1. ``core.paths.setup()`` —— 确保 ``data/``、``logs/`` 存在
2. ``core.config.setup()`` —— 加载 YAML + env 合并配置
3. ``core.logging.setup()`` —— 配置 loguru 分类日志
4. ``ui.app.run()`` —— 启动 PySide6 主窗口

注：本骨架阶段仅落地 ``paths``，其余模块将在后续任务实现。
"""

from __future__ import annotations

import sys


def main() -> int:
    """程序主入口。返回退出码。"""
    # 1. 先确保路径（独立于 config，避免配置加载失败时无目录写日志）
    from points_v2.core import paths

    paths.setup()

    # 2. 加载配置
    try:
        from points_v2.core import config

        config.setup()
    except ImportError:
        # config 模块尚未实现 —— 骨架阶段允许
        print(
            "[points_v2] core.config 尚未实现（骨架阶段），跳过配置加载",
            file=sys.stderr,
        )

    # 3. 启动 UI
    try:
        from points_v2.ui import app as ui_app

        return ui_app.run()
    except ImportError:
        # ui 模块尚未实现 —— 骨架阶段允许
        print(
            "[points_v2] ui.app 尚未实现（骨架阶段）。"
            "已完成：路径初始化、配置加载（如可用）。",
            file=sys.stderr,
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
