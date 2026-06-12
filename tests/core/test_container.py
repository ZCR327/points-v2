"""Tests for points_v2.core.container."""

from __future__ import annotations

import pytest

from points_v2.core.container import Container
from points_v2.core.container import container as default_container


def test_register_and_resolve() -> None:
    """``register`` + ``resolve`` 基础流程。"""
    c = Container()
    c.register("answer", lambda: 42)
    assert c.resolve("answer") == 42


def test_resolve_unknown_raises_keyerror() -> None:
    """未注册 name 应抛 ``KeyError``。"""
    c = Container()
    with pytest.raises(KeyError, match="missing"):
        c.resolve("missing")


def test_register_rejects_bad_args() -> None:
    """空 name / 非 callable factory 应抛错。"""
    c = Container()
    with pytest.raises(ValueError, match="非空字符串"):
        c.register("", lambda: 1)
    with pytest.raises(TypeError, match="可调用对象"):
        c.register("name", 123)  # type: ignore[arg-type]


def test_clear_and_has() -> None:
    """``clear`` 清空；``has`` 查询；``names`` 列出。"""
    c = Container()
    c.register("a", lambda: 1)
    c.register("b", lambda: 2)
    assert c.has("a") and c.has("b")
    assert sorted(c.names()) == ["a", "b"]
    c.clear()
    assert not c.has("a")
    assert c.names() == []


def test_default_container_is_module_singleton() -> None:
    """``points_v2.core.container.container`` 是模块级单例，可被复用。"""
    default_container.register("k", lambda: "v")
    assert default_container.resolve("k") == "v"
    default_container.clear()
