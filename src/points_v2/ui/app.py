"""QApplication 启动入口（ARCHITECTURE §9）。

设计要点
--------

- :func:`create_qt_app` 工厂函数：可重复构造（测试隔离）
- :func:`run` 入口由 :mod:`points_v2.__main__` 调用
- 不在模块层构造 ``QApplication``，避免 import 时副作用
- 启动顺序：``paths.setup`` → ``config.setup`` → ``logging.setup`` →
  service 注入 → ``MainWindow`` 展示
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from PySide6.QtWidgets import QApplication

from points_v2 import __version__

__all__ = ["create_qt_app", "parse_app_args", "run", "main"]


def parse_app_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析 UI 启动参数。

    复用 :mod:`points_v2.__main__` 的 ``--api`` / ``--version`` 行为；
    UI 自身的子参数（窗口大小、主题等）走 :envvar:`QT_*` 标准环境变量。
    """
    parser = argparse.ArgumentParser(
        prog="points_v2-ui",
        description="智能回收社 积分系统 v2 — PySide6 GUI",
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="不创建 QApplication；仅用于在测试/CI 环境 sanity-import",
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
    return parser.parse_args(argv)


def create_qt_app(argv: list[str] | None = None) -> QApplication:
    """构造 :class:`QApplication` 单例（已存在则复用）。

    设置中文应用名（影响 macOS / Linux 桌面环境）。
    """
    app = QApplication.instance()
    if app is None:
        if argv is None:
            argv = sys.argv[:1] or ["points_v2"]
        app = QApplication(argv)
    app.setApplicationName("智能回收社 积分系统")
    app.setApplicationDisplayName("智能回收社 积分系统 v2")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("智能回收社项目组")
    return app


def _bootstrap_core() -> None:
    """路径 → 配置 → 日志（与 api/__main__ 一致，幂等）。"""
    from points_v2.core import config, logging, paths

    paths.setup()
    try:
        config.setup()
    except Exception as exc:  # noqa: BLE001 - 排错模式
        print(f"[points_v2-ui] 配置加载失败：{exc}", file=sys.stderr)
    try:
        logging.setup()
    except Exception as exc:  # noqa: BLE001
        print(f"[points_v2-ui] 日志初始化失败：{exc}", file=sys.stderr)


def _build_services() -> Any:
    """构造 service bundle（复用 :mod:`points_v2.api.app_state`）。"""
    from points_v2.api.app_state import build_default_services

    return build_default_services()


def run() -> int:
    """GUI 入口：创建 QApplication + MainWindow，进入事件循环。

    :returns: QApplication.exec() 返回码。
    """
    args = parse_app_args()
    if args.version:
        print(f"points_v2 {__version__}")
        return 0
    if args.api:
        from points_v2.api import main as api_main

        return api_main()
    if args.no_gui:
        print("[points_v2-ui] --no-gui 模式：未创建 QApplication，退出")
        return 0

    _bootstrap_core()
    app = create_qt_app()
    services = _build_services()
    # 延迟 import：避免在 PySide6 不可用时 import 失败
    from points_v2.ui.main_window import MainWindow

    window = MainWindow(services=services)
    window.show()
    # 关闭主窗口时让事件循环退出
    app.aboutToQuit.connect(window.shutdown)  # type: ignore[arg-type]
    return app.exec()


def main() -> int:
    """脚本入口。"""
    return run()


if __name__ == "__main__":
    sys.exit(main())
