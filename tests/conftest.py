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


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """若 PySide6 不可用，自动跳过所有 UI 测试（避免 CI 装包过重）。

    本地开发 ``pip install -e ".[gui]"`` 后 PySide6 存在，UI 测试正常跑。
    CI 默认装 ``.[dev]`` 不带 PySide6 → 整组 tests/ui 跳过。
    """
    try:
        importlib.import_module("PySide6")
        pyside6_available = True
    except ImportError:
        pyside6_available = False

    if pyside6_available:
        return

    skip_marker = pytest.mark.skip(reason="PySide6 not installed; pip install -e '.[gui]' to enable")
    for item in items:
        # 用 nodeid 而不是 file path（兼容 symlink / absolute path）
        if "tests/ui" in str(item.fspath).replace("\\", "/"):
            item.add_marker(skip_marker)
