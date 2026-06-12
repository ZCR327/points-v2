"""Test for the high-level points_v2.core.setup() entry point."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_core_setup_initializes_paths_config_logging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reset_config: None
) -> None:
    """``points_v2.core.setup()`` 一站式：路径 + 配置 + 日志。"""
    # 准备临时 config + log 目录
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    log_dir = tmp_path / "logs"
    (config_dir / "default.yaml").write_text(
        "app:\n  name: 'CoreSetupTest'\nlogging:\n  level: INFO\n",
        encoding="utf-8",
    )
    (config_dir / "development.yaml").write_text("{}", encoding="utf-8")

    from points_v2.core import config, paths
    from points_v2.core import logging as core_logging
    from points_v2.core import setup as core_setup

    monkeypatch.setattr(paths, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(paths, "LOGS_DIR", log_dir)
    # paths.setup() 会创建 DATA_DIR / LOGS_DIR / BACKUP_DIR
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(paths, "BACKUP_DIR", tmp_path / "data" / "backups")

    # 重置 config 缓存让 monkeypatch 生效
    config._config = None  # type: ignore[attr-defined]
    core_setup()
    # config 应该加载到新数据
    assert config.get("app.name") == "CoreSetupTest"
    # 日志目录已建
    assert log_dir.is_dir()
    # loguru sink 已被设置
    assert core_logging._sink_id_file is not None
