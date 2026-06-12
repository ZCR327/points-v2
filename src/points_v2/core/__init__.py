"""Core infrastructure layer: paths / config / logging / exceptions / DI.

典型启动顺序（在 ``__main__`` 或服务入口调用）::

    from points_v2.core import setup
    setup()           # 一次性：路径 + 配置 + 日志
"""

from __future__ import annotations

from points_v2.core import container, exceptions, logging, paths
from points_v2.core.config import get_config, reload_config


def setup() -> None:
    """一次性初始化：路径 → 配置 → 日志。

    幂等：可重复调用（``logging.setup()`` 会先 ``remove`` 旧 sink）。
    """
    paths.setup()
    config_setup()  # 显式函数名避免与本函数同名遮蔽
    logging.setup()


# 内部别名：把 ``config.setup`` 提到模块层避免循环
def config_setup() -> None:
    """加载并缓存配置（异常直接向上抛）。"""
    from points_v2.core import config as _config_mod

    _config_mod.setup()


__all__ = [
    "setup",
    "config_setup",
    "container",
    "exceptions",
    "logging",
    "paths",
    "get_config",
    "reload_config",
]
