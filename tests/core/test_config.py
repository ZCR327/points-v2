"""Tests for points_v2.core.config."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_setup_loads_default_yaml(tmp_config_dir: Path, reset_config: None) -> None:
    """``setup()`` 应合并 default.yaml + development.yaml。"""
    from points_v2.core import config

    cfg = config.setup()
    assert cfg["app"]["name"] == "TestApp"
    # development.yaml 覆盖
    assert cfg["app"]["debug"] is True
    # logging 合并
    assert cfg["logging"]["level"] == "DEBUG"


def test_get_config_returns_deepcopy(tmp_config_dir: Path, reset_config: None) -> None:
    """``get_config()`` 必须返回深拷贝，修改不应影响缓存。"""
    from points_v2.core import config

    config.setup()
    cfg1 = config.get_config()
    cfg1["app"]["name"] = "MUTATED"
    cfg2 = config.get_config()
    assert cfg2["app"]["name"] == "TestApp"


def test_env_var_overrides_yaml(
    tmp_config_dir: Path, reset_config: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``POINTS_V2_API__PORT=9999`` 应覆盖 yaml 中的 api.port。"""
    from points_v2.core import config

    (tmp_config_dir / "default.yaml").write_text(
        "app:\n  name: 'X'\napi:\n  port: 8765\n",
        encoding="utf-8",
    )
    (tmp_config_dir / "development.yaml").write_text("app: {}\n", encoding="utf-8")
    monkeypatch.setenv("POINTS_V2_API__PORT", "9999")
    cfg = config.setup()
    assert cfg["api"]["port"] == 9999
    # 原 yaml 中的其它字段仍在
    assert cfg["app"]["name"] == "X"


def test_env_var_coercion(
    tmp_config_dir: Path, reset_config: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """env 字符串 → bool / int / float / str 自动转换。"""
    from points_v2.core import config

    (tmp_config_dir / "default.yaml").write_text(
        "app:\n  name: 'X'\nflags: {}\nnumbers: {}\n",
        encoding="utf-8",
    )
    (tmp_config_dir / "development.yaml").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("POINTS_V2_FLAGS__ENABLED", "true")
    monkeypatch.setenv("POINTS_V2_FLAGS__DISABLED", "false")
    monkeypatch.setenv("POINTS_V2_NUMBERS__INT", "42")
    monkeypatch.setenv("POINTS_V2_NUMBERS__FLOAT", "3.14")
    monkeypatch.setenv("POINTS_V2_NUMBERS__RAW", "hello")
    cfg = config.setup()
    assert cfg["flags"]["enabled"] is True
    assert cfg["flags"]["disabled"] is False
    assert cfg["numbers"]["int"] == 42
    assert cfg["numbers"]["float"] == 3.14
    assert cfg["numbers"]["raw"] == "hello"


def test_get_by_dotted_path(tmp_config_dir: Path, reset_config: None) -> None:
    """``get("a.b.c")`` 按点号取值。"""
    from points_v2.core import config

    (tmp_config_dir / "default.yaml").write_text(
        "a:\n  b:\n    c: 123\n  missing: null\n", encoding="utf-8"
    )
    (tmp_config_dir / "development.yaml").write_text("{}", encoding="utf-8")
    config.setup()
    assert config.get("a.b.c") == 123
    assert config.get("a.b.nonexistent", "fallback") == "fallback"
    assert config.get("totally.absent") is None
