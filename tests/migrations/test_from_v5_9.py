"""Tests for ``points_v2.migrations.from_v5_9``.

覆盖：

- ASCII 用户名（向后兼容）
- 中文 / CJK 用户名（v5.9 老数据）
- 混合（中英数字）
- user.points 从 records 算最后 balance_after
- 临时密码生成 + 写入 report.new_passwords
- username_to_id 映射
- 失败用户名（带空格 / 控制字符）记入 errors 但不阻塞
- 孤立 records（user 未导入）被跳过
- dry-run 不写文件
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from points_v2.migrations.from_v5_9 import run_migration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _write_marks(path: Path, users: dict[str, dict]) -> None:
    (path / "marks.json").write_text(
        json.dumps({"users": users}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_history(path: Path, records: list[dict]) -> None:
    (path / "points_history.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@pytest.fixture
def v59_dir(tmp_path: Path) -> Path:
    """v5.9 数据源目录（含 marks.json + points_history.json）。"""
    d = tmp_path / "v59"
    d.mkdir()
    return d


@pytest.fixture
def v2_dir(tmp_path: Path) -> Path:
    """v2 目标目录。"""
    d = tmp_path / "v2"
    d.mkdir()
    return d


def _ascii_user(name: str = "alice", points: int = 0) -> dict:
    return {
        "password_hash": "h" * 64,
        "salt": "s" * 64,
        "points": points,
        "role": "user",
        "created_at": "2026-04-14 17:26:04",
    }


def _cjk_user(name: str = "赵昶", role: str = "admin") -> dict:
    return {
        "password_hash": "h" * 64,
        "salt": "s" * 64,
        "points": 0,
        "role": role,
        "created_at": "2026-04-14 18:32:17",
    }


# ---------------------------------------------------------------------------
# ASCII 用户
# ---------------------------------------------------------------------------
def test_migrate_ascii_user_basic(v59_dir: Path, v2_dir: Path) -> None:
    """纯 ASCII 用户正常迁移。"""
    _write_marks(v59_dir, {"alice": _ascii_user("alice")})
    _write_history(v59_dir, [])

    report = run_migration(v59_dir, v2_dir)

    assert report.users_imported == 1
    assert report.users_failed == 0
    assert report.records_imported == 0

    users = json.loads((v2_dir / "users.json").read_text(encoding="utf-8"))
    assert len(users) == 1
    assert users[0]["username"] == "alice"
    assert users[0]["role"] == "user"
    assert users[0]["password_hash"].startswith("$2b$")  # bcrypt


# ---------------------------------------------------------------------------
# CJK 用户（核心：v5.9 兼容性）
# ---------------------------------------------------------------------------
def test_migrate_cjk_user_accepted(v59_dir: Path, v2_dir: Path) -> None:
    """2 字汉字用户名应被接受（之前 v2 schema 拒绝）。"""
    _write_marks(v59_dir, {"赵昶": _cjk_user("赵昶")})
    _write_history(v59_dir, [])

    report = run_migration(v59_dir, v2_dir)

    assert report.users_imported == 1, (
        f"赵昶 should be importable, errors: {report.errors}"
    )
    assert report.users_failed == 0

    users = json.loads((v2_dir / "users.json").read_text(encoding="utf-8"))
    assert users[0]["username"] == "赵昶"
    assert users[0]["id"]  # 新生成 uuid


def test_migrate_cjk_and_ascii_mixed(v59_dir: Path, v2_dir: Path) -> None:
    """ASCII + CJK 混合用户都进。"""
    _write_marks(
        v59_dir,
        {
            "admin": _ascii_user("admin", points=0),
            "zcr": _ascii_user("zcr", points=25),
            "赵昶": _cjk_user("赵昶"),
            "唐荣": _cjk_user("唐荣"),
        },
    )
    _write_history(v59_dir, [])

    report = run_migration(v59_dir, v2_dir)

    assert report.users_total == 4
    assert report.users_imported == 4
    assert report.users_failed == 0

    users = {u["username"] for u in json.loads((v2_dir / "users.json").read_text(encoding="utf-8"))}
    assert users == {"admin", "zcr", "赵昶", "唐荣"}


# ---------------------------------------------------------------------------
# user.points 回填
# ---------------------------------------------------------------------------
def test_user_points_backfilled_from_records(v59_dir: Path, v2_dir: Path) -> None:
    """zcr 在 v5.9 有 2 条 records（10 + 15），迁移后 user.points=25。"""
    _write_marks(v59_dir, {"zcr": _ascii_user("zcr", points=0)})
    _write_history(
        v59_dir,
        [
            {
                "username": "zcr",
                "change": 10,
                "old_points": 0,
                "new_points": 10,
                "operator": "zcr",
                "operation_type": "task",
                "timestamp": "2026-06-04 21:59:45",
            },
            {
                "username": "zcr",
                "change": 15,
                "old_points": 10,
                "new_points": 25,
                "operator": "zcr",
                "operation_type": "task",
                "timestamp": "2026-06-04 21:59:47",
            },
        ],
    )

    report = run_migration(v59_dir, v2_dir)
    assert report.users_imported == 1
    assert report.records_imported == 2

    users = json.loads((v2_dir / "users.json").read_text(encoding="utf-8"))
    zcr = next(u for u in users if u["username"] == "zcr")
    assert zcr["points"] == 25, "zcr.points should equal latest balance_after"


def test_user_points_unaffected_when_no_records(v59_dir: Path, v2_dir: Path) -> None:
    """无 records 时 user.points 保持 marks.json 原值。"""
    _write_marks(v59_dir, {"admin": _ascii_user("admin", points=42)})
    _write_history(v59_dir, [])

    report = run_migration(v59_dir, v2_dir)
    assert report.records_imported == 0

    users = json.loads((v2_dir / "users.json").read_text(encoding="utf-8"))
    assert users[0]["points"] == 42


# ---------------------------------------------------------------------------
# CJK 用户的 records 也能迁
# ---------------------------------------------------------------------------
def test_cjk_user_records_also_migrated(v59_dir: Path, v2_dir: Path) -> None:
    """中文用户的积分流水也能进 v2（user_id 正确映射）。"""
    _write_marks(v59_dir, {"唐荣": _cjk_user("唐荣", role="user")})
    _write_history(
        v59_dir,
        [
            {
                "username": "唐荣",
                "change": 5,
                "new_points": 5,
                "operator": "admin",
                "operation_type": "task",
                "timestamp": "2026-06-04 22:00:00",
            },
        ],
    )

    report = run_migration(v59_dir, v2_dir)
    assert report.records_imported == 1

    records = json.loads((v2_dir / "points.json").read_text(encoding="utf-8"))
    users = json.loads((v2_dir / "users.json").read_text(encoding="utf-8"))

    user_id = users[0]["id"]
    assert records[0]["user_id"] == user_id
    assert users[0]["points"] == 5


# ---------------------------------------------------------------------------
# 临时密码 + username_to_id
# ---------------------------------------------------------------------------
def test_temp_passwords_and_id_mapping(v59_dir: Path, v2_dir: Path) -> None:
    """每个成功导入的 user 都拿一个临时密码（bcrypt hash 写入 users.json）。"""
    _write_marks(
        v59_dir,
        {
            "admin": _ascii_user("admin"),
            "zcr": _ascii_user("zcr"),
        },
    )
    _write_history(v59_dir, [])

    report = run_migration(v59_dir, v2_dir)

    # 临时密码 report
    assert set(report.new_passwords.keys()) == {"admin", "zcr"}
    assert all(len(p) >= 8 for p in report.new_passwords.values())

    # username_to_id 映射
    users = json.loads((v2_dir / "users.json").read_text(encoding="utf-8"))
    by_username = {u["username"]: u["id"] for u in users}
    assert report.username_to_id == by_username

    # bcrypt hash 真的写进 users.json
    for u in users:
        assert u["password_hash"].startswith("$2b$")
        assert u["password_hash"] != "h" * 64  # 不是 v5.9 那个 sha256


def test_two_runs_produce_different_temp_passwords(v59_dir: Path, v2_dir: Path) -> None:
    """每次跑都生成新临时密码（不可预测性 + 旧 hash 立即作废）。"""
    _write_marks(v59_dir, {"alice": _ascii_user("alice")})
    _write_history(v59_dir, [])

    r1 = run_migration(v59_dir, v2_dir)
    r2 = run_migration(v59_dir, v2_dir)
    assert r1.new_passwords["alice"] != r2.new_passwords["alice"]


# ---------------------------------------------------------------------------
# 失败用户：记入 errors 但不阻塞
# ---------------------------------------------------------------------------
def test_invalid_username_recorded_as_failure(v59_dir: Path, v2_dir: Path) -> None:
    """含非法字符的用户名（空格、反斜杠）应记入 errors。"""
    _write_marks(
        v59_dir,
        {
            "alice": _ascii_user("alice"),
            "bad name": _ascii_user("bad name"),  # 包含空格
            "tab\\there": _ascii_user("tab\\there"),  # 字面反斜杠（写入 JSON 后 Python repr 会再加 1 个 \）
        },
    )
    _write_history(v59_dir, [])

    report = run_migration(v59_dir, v2_dir)

    assert report.users_imported == 1
    assert report.users_failed == 2
    assert len(report.errors) == 2
    assert any("bad name" in e for e in report.errors)
    # {username!r} 把 username repr 一次，原始 1 个 \ 变 2 个 \\
    assert any("tab\\\\there" in e for e in report.errors)

    users = json.loads((v2_dir / "users.json").read_text(encoding="utf-8"))
    assert [u["username"] for u in users] == ["alice"]


def test_orphan_records_skipped(v59_dir: Path, v2_dir: Path) -> None:
    """records 引用未导入的用户（中文名失败）→ 流水丢弃，记入 errors。"""
    _write_marks(v59_dir, {"alice": _ascii_user("alice")})
    _write_history(
        v59_dir,
        [
            {
                "username": "alice",
                "change": 10,
                "new_points": 10,
                "operator": "alice",
                "operation_type": "task",
                "timestamp": "2026-06-04 21:00:00",
            },
            {
                "username": "不存在的人",  # 不会出现在 marks.json
                "change": 5,
                "new_points": 5,
                "operator": "system",
                "operation_type": "task",
                "timestamp": "2026-06-04 21:01:00",
            },
        ],
    )

    report = run_migration(v59_dir, v2_dir)
    assert report.records_imported == 1  # 只有 alice 的进了
    assert report.records_failed == 1
    assert any("不存在的人" in e for e in report.errors)


# ---------------------------------------------------------------------------
# dry-run
# ---------------------------------------------------------------------------
def test_dry_run_writes_nothing(v59_dir: Path, v2_dir: Path) -> None:
    """--dry-run 不创建任何目标文件。"""
    _write_marks(v59_dir, {"alice": _ascii_user("alice")})
    _write_history(v59_dir, [])

    report = run_migration(v59_dir, v2_dir, dry_run=True)
    assert report.dry_run is True
    assert report.users_imported == 1

    assert not (v2_dir / "users.json").exists()
    assert not (v2_dir / "points.json").exists()


# ---------------------------------------------------------------------------
# 报告文件
# ---------------------------------------------------------------------------
def test_migration_report_written(v59_dir: Path, v2_dir: Path) -> None:
    """run_migration 落盘后，target/migration_report.json 存在且结构正确。"""
    _write_marks(v59_dir, {"admin": _ascii_user("admin")})
    _write_history(v59_dir, [])

    run_migration(v59_dir, v2_dir)
    report_path = v2_dir / "migration_report.json"
    assert report_path.exists()

    body = json.loads(report_path.read_text(encoding="utf-8"))
    assert body["summary"]["users"]["imported"] == 1
    assert "admin" in body["new_passwords"]
    assert "admin" in body["username_to_id"]


# ---------------------------------------------------------------------------
# 角色映射
# ---------------------------------------------------------------------------
def test_role_mapping(v59_dir: Path, v2_dir: Path) -> None:
    """v5.9 super_admin/admin/user 正确映射到 v2 UserRole。"""
    _write_marks(
        v59_dir,
        {
            "boss": {**_ascii_user("boss"), "role": "super_admin"},
            "mgr": {**_ascii_user("mgr"), "role": "admin"},
            "alice": {**_ascii_user("alice"), "role": "user"},
        },
    )
    _write_history(v59_dir, [])

    report = run_migration(v59_dir, v2_dir)
    assert report.users_imported == 3

    users = {u["username"]: u["role"] for u in json.loads((v2_dir / "users.json").read_text(encoding="utf-8"))}
    assert users == {"boss": "super_admin", "mgr": "admin", "alice": "user"}
