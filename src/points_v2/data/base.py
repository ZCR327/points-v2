"""Generic JSON-backed repository (ARCHITECTURE §6).

设计要点
--------

- **类型参数** ``T`` 由 Pydantic BaseModel 子类约束
- **内存镜像**：启动时 ``load()`` 一次性读入，**所有查询**都走内存 dict（O(1) lookup）
- **原子写**：写文件时先写 ``*.tmp``，再 ``os.replace``（POSIX/Win 都原子）
- **线程安全**：所有读写都在 ``threading.RLock`` 守护下，避免并发损坏
- **追加 API** 不存在（Repository 应保持简洁）；业务侧用 ``insert``/``update``/``delete``

设计契约
--------

子类必须实现：

- :pyattr:`_FILENAME` —— 相对 ``data_dir`` 的文件名
- :py:meth:`_pk` —— 返回领域对象的唯一键（默认 ``obj.id``）

提供：

- ``load()`` / ``save()`` —— 显式控制（默认惰性 + 自动 save）
- ``find(predicate)`` / ``find_one(predicate)`` —— 内存过滤
- ``get(pk)`` —— O(1) 取单个
- ``insert(obj)`` / ``update(obj)`` / ``delete(pk)`` —— 写并自动 save
- ``all()`` / ``count()`` —— 全量
- ``clear()`` —— 清空（测试用）
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from points_v2.core import paths
from points_v2.core.exceptions import StorageError

# 受 pydantic 约束的领域对象
T = TypeVar("T", bound=BaseModel)


class JsonRepository(Generic[T]):
    """JSON 文件 Repository 抽象基类。

    使用示例::

        class UserRepository(JsonRepository[User]):
            _FILENAME = "users.json"

            def _pk(self, obj: User) -> str:
                return obj.id

        repo = UserRepository()
        repo.load()
        repo.insert(User(username="alice", ...))
    """

    _FILENAME: str = ""  # 子类必须覆盖

    # ------------------------------------------------------------------------
    # 构造 / 状态
    # ------------------------------------------------------------------------
    def __init__(self, base_dir: Path | None = None) -> None:
        if not self._FILENAME:
            raise StorageError(
                "JsonRepository 子类必须定义 _FILENAME",
                details={"cls": type(self).__name__},
            )
        self._base_dir: Path = base_dir or paths.DATA_DIR
        self._file: Path = self._base_dir / self._FILENAME
        self._items: dict[str, T] = {}
        self._lock: threading.RLock = threading.RLock()
        self._loaded: bool = False

    # ------------------------------------------------------------------------
    # 必须由子类实现
    # ------------------------------------------------------------------------
    def _pk(self, obj: T) -> str:
        """返回 obj 的主键。默认 ``obj.id``。"""
        return obj.id  # type: ignore[attr-defined, no-any-return]

    # ------------------------------------------------------------------------
    # 文件 IO
    # ------------------------------------------------------------------------
    def load(self) -> None:
        """从磁盘加载全量数据到内存。**已加载则跳过**——调用 :meth:`clear` 强制重读。"""
        with self._lock:
            if self._loaded:
                return
            self._items = self._read_file()
            self._loaded = True

    def save(self) -> None:
        """把内存 dict 原子写到磁盘。**总是**写（即使无变化）。"""
        with self._lock:
            self._write_file(self._items)

    def reload(self) -> None:
        """强制重读。**测试用**。"""
        with self._lock:
            self._items = self._read_file()
            self._loaded = True

    # ------------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------------
    def insert(self, obj: T) -> T:
        """插入新对象；pk 重复抛 :class:`DuplicateUserError`/``ValueError``。"""
        with self._lock:
            self._ensure_loaded()
            pk = self._pk(obj)
            if pk in self._items:
                raise ValueError(
                    f"{type(self).__name__}.insert: 主键 {pk!r} 已存在",
                )
            self._items[pk] = obj
            self.save()
            return obj

    def update(self, obj: T) -> T:
        """按 pk 替换；不存在抛 :class:`KeyError`。"""
        with self._lock:
            self._ensure_loaded()
            pk = self._pk(obj)
            if pk not in self._items:
                raise KeyError(
                    f"{type(self).__name__}.update: 主键 {pk!r} 不存在",
                )
            self._items[pk] = obj
            self.save()
            return obj

    def upsert(self, obj: T) -> T:
        """存在则 update，不存在则 insert。"""
        with self._lock:
            self._ensure_loaded()
            pk = self._pk(obj)
            self._items[pk] = obj
            self.save()
            return obj

    def delete(self, pk: str) -> bool:
        """按 pk 删除；返回 ``True`` 表示真的删了。"""
        with self._lock:
            self._ensure_loaded()
            if pk not in self._items:
                return False
            del self._items[pk]
            self.save()
            return True

    def get(self, pk: str) -> T | None:
        with self._lock:
            self._ensure_loaded()
            return self._items.get(pk)

    def find(self, predicate: Callable[[T], bool]) -> list[T]:
        """内存过滤，返回所有满足条件的对象。"""
        with self._lock:
            self._ensure_loaded()
            return [obj for obj in self._items.values() if predicate(obj)]

    def find_one(self, predicate: Callable[[T], bool]) -> T | None:
        """返回第一个满足条件的对象（或 ``None``）。"""
        with self._lock:
            self._ensure_loaded()
            for obj in self._items.values():
                if predicate(obj):
                    return obj
            return None

    def all(self) -> list[T]:
        with self._lock:
            self._ensure_loaded()
            return list(self._items.values())

    def count(self) -> int:
        with self._lock:
            self._ensure_loaded()
            return len(self._items)

    def clear(self) -> None:
        """清空（**测试用**）；同时写空数组到磁盘。"""
        with self._lock:
            self._items.clear()
            self.save()
            self._loaded = True

    # ------------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------------
    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def _read_file(self) -> dict[str, T]:
        """读 JSON 数组并按 pk 索引。文件不存在 → 空 dict。"""
        if not self._file.exists():
            return {}
        try:
            raw = self._file.read_text(encoding="utf-8")
        except OSError as exc:
            raise StorageError(
                f"读取数据文件失败: {self._file}",
                details={"path": str(self._file), "error": str(exc)},
            ) from exc
        if not raw.strip():
            return {}
        try:
            data: list[dict[str, Any]] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise StorageError(
                f"JSON 解析失败: {self._file}",
                details={"path": str(self._file), "line": exc.lineno, "col": exc.colno},
            ) from exc
        if not isinstance(data, list):
            raise StorageError(
                f"JSON 顶层必须是数组: {self._file}",
                details={"path": str(self._file), "type": type(data).__name__},
            )
        model_cls = self._model_class()
        items: dict[str, T] = {}
        for entry in data:
            try:
                obj = model_cls.model_validate(entry)
            except ValidationError as exc:
                raise StorageError(
                    f"记录校验失败: {self._file}",
                    details={"entry": entry, "errors": exc.errors()},
                ) from exc
            items[self._pk(obj)] = obj
        return items

    def _write_file(self, items: dict[str, T]) -> None:
        """原子写：先 ``*.tmp``，再 ``os.replace``。"""
        self._base_dir.mkdir(parents=True, exist_ok=True)
        payload = [obj.model_dump(mode="json") for obj in items.values()]
        tmp = self._file.with_suffix(self._file.suffix + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self._file)
        except OSError as exc:
            raise StorageError(
                f"写入数据文件失败: {self._file}",
                details={"path": str(self._file), "error": str(exc)},
            ) from exc
        finally:
            with contextlib.suppress(OSError):
                if tmp.exists():
                    tmp.unlink()

    def _model_class(self) -> type[T]:
        """子类可覆盖以显式指定 model 类（用于类型推断）。"""
        for base in getattr(type(self), "__orig_bases__", ()):
            args = getattr(base, "__args__", ())
            if args:
                return args[0]  # type: ignore[no-any-return]
        # 回退：从 _items 推断
        if self._items:
            first = next(iter(self._items.values()))
            return type(first)
        raise StorageError(
            "JsonRepository._model_class: 无法推断模型类",
            details={"cls": type(self).__name__},
        )


__all__ = ["JsonRepository", "T"]
