"""Entry point for ``python -m points_v2``.

启动模式（CLI 参数）：

- （默认，无参数）→ 启动 PySide6 GUI（尚未实现，目前打印提示后退出）
- ``--api`` → 启动 FastAPI HTTP API（uvicorn）
- ``--version`` → 打印版本号
- ``--help`` → 帮助

启动顺序（每个模式独立走自己的 setup）：
1. ``core.paths.setup()`` —— 确保 ``data/``、``logs/`` 存在
2. ``core.config.setup()`` —— 加载 YAML + env 合并配置
3. ``core.logging.setup()`` —— 配置 loguru 分类日志
4. ``api.main()`` 或 ``ui.app.run()`` —— 启动入口
"""

from __future__ import annotations

import argparse
import sys

__all__ = ["main", "parse_args"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析 CLI 参数。允许测试独立调用。"""
    parser = argparse.ArgumentParser(
        prog="points_v2",
        description="智能回收社 积分系统 v2 — PySide6 GUI / FastAPI HTTP API",
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="启动 FastAPI HTTP API（uvicorn），监听配置中的 api.host:api.port",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="打印版本号后退出",
    )
    parser.add_argument(
        "--no-config",
        action="store_true",
        help="跳过配置加载（仅用于排错；生产不要用）",
    )
    return parser.parse_args(argv)


def _bootstrap(no_config: bool = False) -> None:
    """路径 → 配置 → 日志（幂等）。"""
    from points_v2.core import paths

    paths.setup()
    if not no_config:
        try:
            from points_v2.core import config
            config.setup()
        except Exception as exc:  # noqa: BLE001 - 排错模式允许配置缺失
            print(f"[points_v2] 配置加载失败：{exc}", file=sys.stderr)
    try:
        from points_v2.core import logging
        logging.setup()
    except Exception as exc:  # noqa: BLE001
        print(f"[points_v2] 日志初始化失败：{exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """程序主入口。返回退出码。"""
    args = parse_args(argv)

    if args.version:
        from points_v2 import __version__

        print(f"points_v2 {__version__}")
        return 0

    _bootstrap(no_config=args.no_config)

    if args.api:
        from points_v2.api import main as api_main

        return api_main()

    # 默认：尝试启动 GUI（PySide6 尚未实现 → 友好提示）
    try:
        from points_v2.ui import app as ui_app

        return ui_app.run()
    except ImportError:
        print(
            "[points_v2] ui.app 尚未实现（骨架阶段）。"
            "如需 HTTP API，请使用 `python -m points_v2 --api`。",
            file=sys.stderr,
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
