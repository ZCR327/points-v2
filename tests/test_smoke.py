"""冒烟测试：验证包可导入 + 版本号正确。

每个新环境 / 每次 CI 必须通过这两个测试，否则视为骨架坏了。
"""

from __future__ import annotations


def test_version() -> None:
    """包暴露的 ``__version__`` 应为 ``0.1.0``。"""
    import points_v2

    assert points_v2.__version__ == "0.1.0"


def test_imports() -> None:
    """顶层包可导入，且 ``core.paths`` 模块可访问。"""
    import points_v2
    from points_v2.core import paths

    # paths 模块暴露的关键常量
    assert hasattr(paths, "DATA_DIR")
    assert hasattr(paths, "LOGS_DIR")
    assert hasattr(paths, "setup")


def test_paths_setup_is_idempotent(tmp_path, monkeypatch) -> None:
    """``paths.setup()`` 是幂等的，且能创建所需目录。

    用 ``monkeypatch`` 把所有目录常量重定向到 ``tmp_path``，
    避免污染真实工作目录。
    """
    from points_v2.core import paths

    monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(paths, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(paths, "BACKUP_DIR", tmp_path / "data" / "backups")

    # 第一次调用：创建目录
    paths.setup()
    assert (tmp_path / "data").is_dir()
    assert (tmp_path / "logs").is_dir()
    assert (tmp_path / "data" / "backups").is_dir()

    # 第二次调用：不应抛错
    paths.setup()
