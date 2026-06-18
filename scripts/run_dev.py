#!/usr/bin/env python
"""Development runner — 同时启动 GUI（占位）和 API。

目的：本地开发时一键拉起所有服务，方便演示。

用法::

    python scripts/run_dev.py             # 启动 API（GUI 暂未实现 → 跳过）
    python scripts/run_dev.py --api-only  # 仅启动 API
    python scripts/run_dev.py --port 9000 # 指定端口

注意：本脚本目前是**占位**——骨架阶段 GUI 尚未实现；完整版应：
- 用 ``subprocess.Popen`` 启动 uvicorn
- 在另一个进程启动 GUI（PySide6）
- 捕获 SIGINT 优雅关闭
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path

# 确保 ``src/`` 在 sys.path（pyproject.toml 已配，但 scripts/ 独立运行需要）
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_dev",
        description="智能回收社 积分系统 v2 — 开发模式启动",
    )
    parser.add_argument(
        "--api-only",
        action="store_true",
        help="仅启动 HTTP API（默认占位行为）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="覆盖 api.port（默认从配置读取）",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="覆盖 api.host（默认从配置读取）",
    )
    return parser.parse_args(argv)


def run_api_only(args: argparse.Namespace) -> int:
    """直接调 uvicorn 启动 API。"""
    import uvicorn

    from points_v2.api import create_app
    from points_v2.core import config, paths

    paths.setup()
    with contextlib.suppress(Exception):
        config.setup()

    app = create_app()

    host = args.host or str(config.get("api.host", "127.0.0.1"))
    port = args.port or int(config.get("api.port", 8765))

    print(f"[run_dev] Starting API at http://{host}:{port} (docs at /docs)")
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


def run_full(args: argparse.Namespace) -> int:
    """完整模式：API + GUI。GUI 未实现时降级到 api-only 并提示。"""
    print(
        "[run_dev] GUI 尚未实现，自动降级为 api-only。"
        "如需 GUI，请等待 Track 3 完成。",
        file=sys.stderr,
    )
    return run_api_only(args)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.api_only:
        return run_api_only(args)
    return run_full(args)


if __name__ == "__main__":
    sys.exit(main())
