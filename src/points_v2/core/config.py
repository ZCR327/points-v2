"""Configuration loader: YAML + environment variable merge.

设计要点
--------

- 加载顺序（ARCHITECTURE §4.4）：``default.yaml`` → ``{APP_ENV}.yaml`` → 环境变量
- YAML 用 PyYAML 解析（``safe_load``，禁 ``unsafe_load`` 防止反序列化炸弹）
- 环境变量前缀 ``POINTS_V2_``，分隔符 ``__`` 表示层级，例如
  ``POINTS_V2_API__PORT=9000`` 覆盖 ``api.port = 8765``
- **不修改原始 yaml**——逐层 deep-merge，结果用 ``types.SimpleNamespace`` / dict 暴露
- ``reload_config()`` 用于测试：丢弃缓存重新加载
- ``get_config()`` 返回当前快照 dict，**调用方不应原地修改**——要改用 reload

设计契约
--------
::

    cfg = get_config()
    cfg["api"]["port"]            # int
    cfg["security"]["password_min_length"]  # int
"""

from __future__ import annotations

import copy
import os
import threading
from pathlib import Path
from typing import Any

import yaml

from points_v2.core import paths
from points_v2.core.exceptions import ConfigError

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
ENV_PREFIX: str = "POINTS_V2_"
ENV_DELIMITER: str = "__"
DEFAULT_ENV: str = "development"

_ENV_KEY: str = "APP_ENV"
_CONFIG_KEY: str = "POINTS_V2_CONFIG"

# ---------------------------------------------------------------------------
# 内部状态（受锁保护）
# ---------------------------------------------------------------------------
_lock: threading.RLock = threading.RLock()
_config: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# 工具：深合并 + 环境变量展开
# ---------------------------------------------------------------------------
def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """递归合并 dict；``override`` 优先。**不修改入参**。"""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _load_yaml(path: Path) -> dict[str, Any]:
    """读取单个 YAML，缺失或空文件返回 ``{}``。"""
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ConfigError(
            f"YAML 解析失败: {path}",
            details={"path": str(path), "error": str(exc)},
        ) from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(
            f"YAML 顶层必须是 mapping，实际 {type(data).__name__}",
            details={"path": str(path)},
        )
    return data


def _apply_env_overrides(cfg: dict[str, Any]) -> dict[str, Any]:
    """把 ``POINTS_V2_FOO__BAR=baz`` 写进 ``cfg["foo"]["bar"]``。"""
    result = copy.deepcopy(cfg)
    for raw_key, raw_value in os.environ.items():
        if not raw_key.startswith(ENV_PREFIX):
            continue
        key_path = raw_key[len(ENV_PREFIX):].lower().split(ENV_DELIMITER.lower())
        if not key_path or not all(key_path):
            continue
        _set_nested(result, key_path, _coerce_env_value(raw_value))
    return result


def _set_nested(d: dict[str, Any], keys: list[str], value: Any) -> None:
    """在嵌套 dict 中按 key 路径写入；中间层不存在则创建。"""
    cursor: Any = d
    for key in keys[:-1]:
        if key not in cursor or not isinstance(cursor[key], dict):
            cursor[key] = {}
        cursor = cursor[key]
    cursor[keys[-1]] = value


def _coerce_env_value(raw: str) -> Any:
    """环境变量都是字符串，尝试转 bool / int / float / JSON；失败则返回原字符串。

    - ``"true"`` / ``"false"``（大小写不敏感）→ bool
    - 全数字 → int
    - 数字带小数点 → float
    - 其余保持 str
    """
    lowered = raw.lower()
    if lowered in ("true", "yes", "on"):
        return True
    if lowered in ("false", "no", "off"):
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _resolve_env_file() -> Path:
    """根据 ``APP_ENV`` 决定要加载的环境特定 YAML 文件。"""
    env = os.environ.get(_ENV_KEY, DEFAULT_ENV).lower() or DEFAULT_ENV
    return paths.config_dir() / f"{env}.yaml"


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------
def setup(*, config_dir: Path | None = None, env: str | None = None) -> dict[str, Any]:
    """加载并缓存配置；可重复调用（会覆盖缓存）。

    :param config_dir: 测试时可注入临时配置目录。
    :param env: 测试时可强制 ``APP_ENV`` 值（不写到 os.environ，只影响本函数）。
    :returns: 合并后的 config dict。
    """
    with _lock:
        global _config
        if env is not None:
            # 临时让 ``_resolve_env_file`` 走测试 env
            previous = os.environ.get(_ENV_KEY)
            os.environ[_ENV_KEY] = env
            try:
                _config = _load_and_merge(config_dir)
            finally:
                if previous is None:
                    os.environ.pop(_ENV_KEY, None)
                else:
                    os.environ[_ENV_KEY] = previous
        else:
            _config = _load_and_merge(config_dir)
        return copy.deepcopy(_config)


def _load_and_merge(config_dir: Path | None) -> dict[str, Any]:
    base_path = (config_dir or paths.config_dir()) / "default.yaml"
    base = _load_yaml(base_path)
    env_path = _resolve_env_file() if config_dir is None else config_dir / (
        f"{os.environ.get(_ENV_KEY, DEFAULT_ENV).lower()}.yaml"
    )
    env_overlay = _load_yaml(env_path)
    merged = _deep_merge(base, env_overlay)
    return _apply_env_overrides(merged)


def get_config() -> dict[str, Any]:
    """返回当前配置快照（深拷贝）；未初始化时**自动调用 :func:`setup`**。"""
    with _lock:
        if _config is None:
            setup()
        assert _config is not None
        return copy.deepcopy(_config)


def reload_config() -> dict[str, Any]:
    """丢弃缓存、重新加载。**测试用**。"""
    with _lock:
        return setup()


def get(key_path: str, default: Any = None) -> Any:
    """按点号路径取值，例如 ``get("api.port")``。"""
    cfg = get_config()
    cursor: Any = cfg
    for part in key_path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return default
        cursor = cursor[part]
    return cursor


__all__ = [
    "ENV_PREFIX",
    "setup",
    "get_config",
    "reload_config",
    "get",
]
