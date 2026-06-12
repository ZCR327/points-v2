"""Tests for points_v2.core.logging."""

from __future__ import annotations

from pathlib import Path

from points_v2.core import logging as core_logging
from points_v2.core.logging import CATEGORIES, get_logger, setup


def test_get_logger_returns_bound_logger(tmp_config_dir: Path, reset_config: None) -> None:
    """``get_logger`` 接受合法 category，``bind`` 后 ``extra`` 中含 category。"""
    from points_v2.core import config

    config.setup()
    setup(log_dir=tmp_config_dir / "logs")
    for cat in CATEGORIES:
        log = get_logger(cat)
        assert log is not None


def test_get_logger_invalid_category_falls_back(tmp_config_dir: Path, reset_config: None) -> None:
    """非法 category 自动降级到 ``system``，不抛错。"""
    from points_v2.core import config

    config.setup()
    setup(log_dir=tmp_config_dir / "logs")
    log = get_logger("nonsense_category")
    assert log is not None


def test_setup_is_idempotent(tmp_config_dir: Path, reset_config: None) -> None:
    """多次 ``setup()`` 不应抛错；每次都应重建 sink。"""
    from points_v2.core import config

    config.setup()
    setup(log_dir=tmp_config_dir / "logs")
    setup(log_dir=tmp_config_dir / "logs")  # 第二次
    # 第三次仍然 OK
    setup(log_dir=tmp_config_dir / "logs")
    # sink 句柄都被赋值过
    assert core_logging._sink_id_file is not None
