"""Categorized loguru setup (ARCHITECTURE §4.2).

设计要点
--------

- 单一全局 sink：文件 + 控制台双输出（文件始终记录，stderr 跟随 ``logging.console`` 配置）
- 文件**按大小轮转**（10MB）、**按时间保留**（30天）
- 分类日志通过 ``logger.bind(category="...")`` 产生——但底层共享一个 file sink
- 调用 :func:`setup` **多次安全**：会 ``remove(0)`` 重建，避免重复输出
- ``serialize=True`` 给文件 sink，**结构化 JSON 方便后续接入 ELK**；
  控制台用人类可读格式

设计契约
--------
::

    from points_v2.core.logging import get_logger
    log = get_logger("points")               # 自动归类 system/points
    log.info("user logged in", user="alice")  # 自动写入 logs/{date}.log
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from loguru import logger

from points_v2.core import config, paths

# ---------------------------------------------------------------------------
# 分类白名单
# ---------------------------------------------------------------------------
CATEGORIES: tuple[str, ...] = (
    "system",
    "login",
    "points",
    "users",
    "sensitive",
)

DEFAULT_CATEGORY: str = "system"

# loguru 自身句柄 id（==0 是默认；setup() 时 remove）
_sink_id_console: int | None = None
_sink_id_file: int | None = None

# loguru 需要 0 个 positional args，但占位让 IDE / mypy 满意
_placeholder: Any = None


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _resolve_level() -> str:
    """从配置读取日志级别；解析失败时退到 INFO。"""
    try:
        level = config.get("logging.level", "INFO")
    except Exception:  # noqa: BLE001 - 配置未加载时最坏退到 INFO
        level = "INFO"
    return str(level).upper()


def _resolve_console() -> bool:
    try:
        return bool(config.get("logging.console", True))
    except Exception:  # noqa: BLE001
        return True


def _resolve_rotation() -> str:
    try:
        return str(config.get("logging.rotation", "10 MB"))
    except Exception:  # noqa: BLE001
        return "10 MB"


def _resolve_retention() -> str:
    try:
        return str(config.get("logging.retention", "30 days"))
    except Exception:  # noqa: BLE001
        return "30 days"


def _resolve_log_file(log_dir: Path) -> Path:
    """分类日志文件名：``points_v2.log``——所有 category 共享一个文件便于 grep。"""
    return log_dir / "points_v2.log"


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------
def setup(*, log_dir: Path | None = None) -> None:
    """初始化 loguru。可重复调用（会清理旧 sink）。"""
    global _sink_id_console, _sink_id_file

    # 1) 清理所有现存 sink（保留 loguru 自己的 default 也清掉，方便重置）
    logger.remove()

    # 2) 解析配置
    target_dir = log_dir or paths.logs_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    level = _resolve_level()
    console = _resolve_console()
    rotation = _resolve_rotation()
    retention = _resolve_retention()

    # 3) 文件 sink（JSON 结构化）
    _sink_id_file = logger.add(
        _resolve_log_file(target_dir),
        level=level,
        rotation=rotation,
        retention=retention,
        encoding="utf-8",
        enqueue=True,        # 线程安全
        backtrace=True,
        diagnose=False,      # 生产不要泄露变量值
        serialize=True,
    )

    # 4) 控制台 sink（人类可读，stderr）
    if console:
        _sink_id_console = logger.add(
            sys.stderr,
            level=level,
            backtrace=True,
            diagnose=False,
            colorize=True,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <7}</level> | "
                "<cyan>{extra[category]}</cyan> | "
                "<level>{message}</level>"
            ),
        )


def get_logger(category: str = DEFAULT_CATEGORY) -> Any:
    """返回带 ``category`` 标签的 logger。

    :param category: 必须在 :data:`CATEGORIES` 内；非法值自动落到 ``system``。
    """
    if category not in CATEGORIES:
        category = DEFAULT_CATEGORY
    return logger.bind(category=category)


__all__ = [
    "CATEGORIES",
    "DEFAULT_CATEGORY",
    "setup",
    "get_logger",
]
