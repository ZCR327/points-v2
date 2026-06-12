"""Path constants and first-run directory initialization.

设计要点
--------
- 所有路径相对**项目根**（即 ``pyproject.toml`` 所在目录），确保开发与打包后行为一致
- 首次运行自动创建 ``data/``、``logs/``、``data/backups/`` 子目录（``exist_ok=True``）
- 使用 ``pathlib.Path`` 而非字符串拼接 —— Windows / POSIX 通用
- 通过 :data:`PROJECT_ROOT` 单例缓存，避免重复解析
- 目录创建是**幂等**的：重复调用 ``setup()`` 不会抛错

设计契约（ARCHITECTURE §6.1）
----------------------------
::

    data/
    ├── users.json
    ├── points.json
    ├── audit.json
    ├── notifications.json
    ├── sessions.json
    ├── settings.json
    ├── products.json
    └── backups/
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# 项目根与目录常量
# ---------------------------------------------------------------------------
# points_v2/core/paths.py → parents[2] = src/ → parents[3] = PROJECT_ROOT
_PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]

DATA_DIR: Path = _PROJECT_ROOT / "data"
LOGS_DIR: Path = _PROJECT_ROOT / "logs"
BACKUP_DIR: Path = DATA_DIR / "backups"
CONFIG_DIR: Path = _PROJECT_ROOT / "config"


def project_root() -> Path:
    """返回项目根目录（``pyproject.toml`` 所在目录）。"""
    return _PROJECT_ROOT


def data_dir() -> Path:
    """返回数据目录（JSON 文件存放处）。"""
    return DATA_DIR


def logs_dir() -> Path:
    """返回日志目录。"""
    return LOGS_DIR


def backup_dir() -> Path:
    """返回备份目录。"""
    return BACKUP_DIR


def config_dir() -> Path:
    """返回配置目录。"""
    return CONFIG_DIR


# ---------------------------------------------------------------------------
# 初始化
# ---------------------------------------------------------------------------
def setup() -> None:
    """确保运行时目录存在。

    幂等操作：重复调用安全。
    应在 ``core.config.setup()`` 之前调用 —— 即使配置加载失败，
    日志目录也已经准备好可以写入崩溃信息。
    """
    for directory in (DATA_DIR, LOGS_DIR, BACKUP_DIR):
        directory.mkdir(parents=True, exist_ok=True)


__all__ = [
    "DATA_DIR",
    "LOGS_DIR",
    "BACKUP_DIR",
    "CONFIG_DIR",
    "project_root",
    "data_dir",
    "logs_dir",
    "backup_dir",
    "config_dir",
    "setup",
]
