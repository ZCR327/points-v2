"""Defensive tests for JsonRepository (base.py) error paths.

We use a tiny in-memory model so we can exercise the error-handling code in
``_read_file`` / ``_write_file`` without depending on the domain layer.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from points_v2.core.exceptions import StorageError
from points_v2.data.base import JsonRepository


class _Mini(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    value: int = 0


class _MiniRepo(JsonRepository[_Mini]):
    _FILENAME = "mini.json"

    def _pk(self, obj: _Mini) -> str:
        return obj.id


def test_empty_file_returns_empty(tmp_data_dir: Path) -> None:
    """文件存在但为空 → 视为 0 记录。"""
    (tmp_data_dir / "mini.json").write_text("", encoding="utf-8")
    repo = _MiniRepo()
    repo.load()
    assert repo.count() == 0


def test_corrupted_json_raises_storage_error(tmp_data_dir: Path) -> None:
    """非合法 JSON 抛 :class:`StorageError`。"""
    (tmp_data_dir / "mini.json").write_text("{not json", encoding="utf-8")
    repo = _MiniRepo()
    with pytest.raises(StorageError, match="JSON 解析失败"):
        repo.load()


def test_top_level_not_array_raises(tmp_data_dir: Path) -> None:
    """顶层必须是数组；dict 会触发 :class:`StorageError`。"""
    (tmp_data_dir / "mini.json").write_text('{"id": "x"}', encoding="utf-8")
    repo = _MiniRepo()
    with pytest.raises(StorageError, match="顶层必须是数组"):
        repo.load()


def test_record_validation_error_raises(tmp_data_dir: Path) -> None:
    """记录字段类型不对 → :class:`StorageError`。"""
    (tmp_data_dir / "mini.json").write_text(
        json.dumps([{"id": "a", "value": "not_an_int"}]),
        encoding="utf-8",
    )
    repo = _MiniRepo()
    with pytest.raises(StorageError, match="记录校验失败"):
        repo.load()


def test_update_unknown_pk_raises_keyerror(tmp_data_dir: Path) -> None:
    """``update`` 不存在的 pk 抛 ``KeyError``。"""
    repo = _MiniRepo()
    obj = _Mini(id="a", value=1)
    with pytest.raises(KeyError, match="不存在"):
        repo.update(obj)


def test_get_missing_returns_none(tmp_data_dir: Path) -> None:
    repo = _MiniRepo()
    repo.load()
    assert repo.get("nope") is None


def test_find_one_returns_none_when_nothing_matches(tmp_data_dir: Path) -> None:
    repo = _MiniRepo()
    repo.insert(_Mini(id="a", value=1))
    assert repo.find_one(lambda x: x.value == 999) is None


def test_upsert_inserts_then_updates(tmp_data_dir: Path) -> None:
    """``upsert`` 在缺失时插入，存在时更新。"""
    repo = _MiniRepo()
    obj = _Mini(id="a", value=1)
    repo.upsert(obj)
    assert repo.get("a").value == 1
    obj2 = _Mini(id="a", value=2)
    repo.upsert(obj2)
    assert repo.get("a").value == 2


def test_clear_empties_repo_and_file(tmp_data_dir: Path) -> None:
    repo = _MiniRepo()
    repo.insert(_Mini(id="a", value=1))
    repo.clear()
    assert repo.count() == 0
    # 文件应写为空数组
    content = json.loads((tmp_data_dir / "mini.json").read_text(encoding="utf-8"))
    assert content == []


def test_reload_forces_reread(tmp_data_dir: Path) -> None:
    """``reload`` 跳过 ``_loaded`` 标志。"""
    repo = _MiniRepo()
    repo.insert(_Mini(id="a", value=1))
    # 手动改文件
    (tmp_data_dir / "mini.json").write_text(
        json.dumps([{"id": "b", "value": 2}]),
        encoding="utf-8",
    )
    # 普通 get 仍是缓存的 a
    assert repo.get("a") is not None
    repo.reload()
    # reload 后 b 出现
    assert repo.get("b") is not None


def test_load_is_idempotent(tmp_data_dir: Path) -> None:
    """``load()`` 第二次调用直接 return。"""
    repo = _MiniRepo()
    repo.load()
    items_count = repo.count()
    # 第二次 load 不应抛错也不应清空
    repo.load()
    assert repo.count() == items_count


def test_base_repo_requires_filename() -> None:
    """``JsonRepository`` 子类未指定 ``_FILENAME`` 时实例化抛 :class:`StorageError`。"""

    class _BadRepo(JsonRepository[_Mini]):
        # 故意不覆盖 _FILENAME
        def _pk(self, obj: _Mini) -> str:  # pragma: no cover
            return obj.id

    with pytest.raises(StorageError, match="_FILENAME"):
        _BadRepo()
