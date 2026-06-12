"""Shared fixtures for the points_v2 test suite."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

# 确保 ``src`` 在 sys.path（pyproject.toml 已配，但保险）
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


@pytest.fixture
def tmp_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """重定向 ``paths.DATA_DIR`` 到临时目录，**所有 repo 都会受影响**。"""
    from points_v2.core import paths

    target = tmp_path / "data"
    target.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(paths, "DATA_DIR", target)
    monkeypatch.setattr(paths, "BACKUP_DIR", target / "backups")
    return target


@pytest.fixture
def tmp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """重定向 ``paths.CONFIG_DIR`` 到临时目录；写入 3 个标准 yaml。"""
    from points_v2.core import paths

    target = tmp_path / "config"
    target.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(paths, "CONFIG_DIR", target)
    (target / "default.yaml").write_text(
        "app:\n  name: 'TestApp'\n  env: development\nlogging:\n  level: INFO\n",
        encoding="utf-8",
    )
    (target / "development.yaml").write_text(
        "app:\n  debug: true\nlogging:\n  level: DEBUG\n",
        encoding="utf-8",
    )
    return target


@pytest.fixture
def reset_config() -> Iterator[None]:
    """重置 core.config 的内部缓存，避免测试间污染。"""
    from points_v2.core import config

    config._config = None  # type: ignore[attr-defined]
    yield
    config._config = None  # type: ignore[attr-defined]


@pytest.fixture
def fresh_container() -> Iterator[None]:
    """每个测试清空进程级 container。"""
    from points_v2.core.container import container

    container.clear()
    yield
    container.clear()


@pytest.fixture
def reload_paths() -> Iterator[None]:
    """如需重新导入 paths（很少用）。"""
    yield
    importlib.reload(importlib.import_module("points_v2.core.paths"))
