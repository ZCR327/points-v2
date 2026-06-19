"""Lightweight dependency injection container (registry pattern).

设计要点
--------

- **够用即可**：单进程内单例 registry，``register(name, factory)`` / ``resolve(name)`` /
  ``has(name)`` / ``clear()``。不引入 ``dependency-injector`` 等三方库。
- **factory 延迟调用**：注册时存 ``lambda``，resolve 时才执行，支持解析时序依赖
  （但请避免循环依赖——那是代码味道）。
- **可替换性**：测试时可以 ``register("user_repo", lambda: FakeUserRepo())``，
  生产用 ``register("user_repo", lambda: UserRepository(...))``。
- **线程安全**：内部用 ``threading.RLock`` 守护 register/resolve/clear 复合操作。
- **失败明确**：`resolve` 未注册时抛 :class:`KeyError`，让 bug 早期暴露。

设计契约（ARCHITECTURE §4.2）
-----------------------------
::

    container.register("user_service", lambda: UserService(...))
    svc = container.resolve("user_service")
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any


class Container:
    """进程级单例 DI 容器。

    用法::

        c = Container()
        c.register("logger", lambda: get_logger("app"))
        logger = c.resolve("logger")
    """

    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], Any]] = {}
        self._lock: threading.RLock = threading.RLock()

    def register(self, name: str, factory: Callable[[], Any]) -> None:
        """注册一个工厂。重复注册会覆盖（用于测试替换）。

        :param name: 注册名。
        :param factory: 无参可调用对象；返回要注入的实例。
        """
        if not name or not isinstance(name, str):
            raise ValueError("Container.register: 'name' 必须是非空字符串")
        if not callable(factory):
            raise TypeError(
                f"Container.register: 'factory' 必须是可调用对象，got {type(factory).__name__}"
            )
        with self._lock:
            self._factories[name] = factory

    def resolve(self, name: str) -> Any:
        """解析并返回注册实例。**每次 resolve 都会调用 factory**，调用方自行缓存。

        :raises KeyError: ``name`` 未注册。
        """
        with self._lock:
            if name not in self._factories:
                raise KeyError(f"Container.resolve: '{name}' 未注册")
            factory = self._factories[name]
        return factory()

    def has(self, name: str) -> bool:
        """检查 ``name`` 是否已注册。"""
        with self._lock:
            return name in self._factories

    def clear(self) -> None:
        """清空所有注册。**测试用**。"""
        with self._lock:
            self._factories.clear()

    def names(self) -> list[str]:
        """返回当前所有注册名（**快照**，不保证 resolve 时仍存在）。"""
        with self._lock:
            return list(self._factories.keys())


# ---------------------------------------------------------------------------
# 进程级默认单例 —— 业务代码用 ``container`` 即可
# ---------------------------------------------------------------------------
container: Container = Container()

__all__ = ["Container", "container"]
