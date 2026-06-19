"""数据迁移：从 v5.9 旧版（基于散落 JSON）导入到 v2 的 JsonRepository 格式。

v5.9 数据布局
------------

- ``data/marks.json`` —— 字典，键为 username，值含 ``password_hash``、``salt``、
  ``points``、``role``、``created_at``、``last_login``、``password_changed``、
  ``disabled``（可选）
- ``data/points_history.json`` —— list，每条含 ``username``、``change``、
  ``old_points``、``new_points``、``operator``、``operation_type``、``timestamp``、
  ``reason``
- ``data/audit_log.json`` —— list（v5.9 不写审计；为空）
- ``data/notifications.json`` —— list（v5.9 默认空）
- ``data/groups.json`` —— v5.9 的 group 概念（v2 不支持，跳过）
- ``data/products.json`` —— v5.9 的积分商城（v2 不支持，跳过）
- ``data/plugins.json`` / ``data/feedback.json`` / ``data/approvals.json`` —
  v5.9 的扩展数据，v2 不支持，**保留在 source 但不导入**

v2 数据布局（ARCHITECTURE §6.1）
------------------------------

- ``data/users.json`` —— list[User]
- ``data/points.json`` —— list[PointsRecord]
- ``data/audit.json`` —— list[AuditLog]
- ``data/notifications.json`` —— list[Notification]

字段映射
--------

marks.json[username] → User:

- id: 重新生成（uuid4 hex），但 username 保持不变
- username: 原样（**必须**通过 v2 的 ``_USERNAME_RE``；中文/特殊字符会失败 →
  此时记录为 skip 并写入报告）
- display_name: 缺失 → 用 username
- role: v5.9 有 ``super_admin`` / ``admin`` / ``user``（v2 同名 enum；忽略大小写）
- points: 原样
- password_hash: v5.9 用 SHA256 + salt，v2 用 bcrypt。**生成新随机密码并 bcrypt 哈希**，
  新密码写入 :file:`migration_report.json` 让管理员分发
- is_active: ``not disabled``
- is_locked: 永远 False
- failed_login_count: 0
- created_at / updated_at: 解析 v5.9 的 ``created_at``（无 → 当前时间）
- last_login_at: 解析 v5.9 的 ``last_login``（无 → None）

points_history.json[i] → PointsRecord:

- id: 重新生成
- user_id: 通过 username 映射到 v2 的 user.id（**只对成功导入的 user**）
- operation: v5.9 ``operation_type`` 字符串 → :class:`OperationType`（未知值 → ``ADJUST``）
- amount: ``change`` 绝对值
- balance_after: ``new_points``
- reason: 原样
- operator_id: 旧 username → 新 id（找不到 → None）
- created_at: 解析 ``timestamp``

幂等
----

- 用户：按 ``username`` 去重；同 username 跳过，**但**记入 report
- 流水：按 ``(user_id, timestamp, change, reason)`` 元组去重

CLI
---

::

    python -m points_v2.migrations.from_v5_9 \\
        --source <v5.9_数据目录> \\
        --target <v2_数据目录> \\
        [--dry-run] \\
        [--report <报告.json>]

设计契约
--------

- :func:`run_migration` 是纯函数：接受 source / target 路径，返回 :class:`MigrationReport`
- 不抛异常（除非必要）；问题写到 report 里
- ``--dry-run`` 不写任何文件，只生成 report
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import string
import sys
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from points_v2.core.exceptions import MigrationError
from points_v2.core.logging import get_logger
from points_v2.domain.enums import OperationType, UserRole
from points_v2.domain.points import MAX_AMOUNT
from points_v2.domain.user import User
from points_v2.utils.hashing import hash_password

__all__ = [
    "MigrationReport",
    "run_migration",
    "parse_timestamp",
    "parse_args",
    "main",
]


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------
@dataclass
class MigrationReport:
    """迁移结果汇总。"""

    users_total: int = 0
    users_imported: int = 0
    users_skipped: int = 0
    users_failed: int = 0
    records_total: int = 0
    records_imported: int = 0
    records_skipped: int = 0
    records_failed: int = 0
    new_passwords: dict[str, str] = field(default_factory=dict)
    username_to_id: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "users": {
                    "total": self.users_total,
                    "imported": self.users_imported,
                    "skipped": self.users_skipped,
                    "failed": self.users_failed,
                },
                "records": {
                    "total": self.records_total,
                    "imported": self.records_imported,
                    "skipped": self.records_skipped,
                    "failed": self.records_failed,
                },
                "dry_run": self.dry_run,
            },
            "new_passwords": self.new_passwords,
            "username_to_id": self.username_to_id,
            "errors": self.errors,
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")
_OPERATION_MAP: dict[str, OperationType] = {
    "earn": OperationType.EARN,
    "spend": OperationType.SPEND,
    "transfer_in": OperationType.TRANSFER_IN,
    "transfer_out": OperationType.TRANSFER_OUT,
    "adjust": OperationType.ADJUST,
    "refund": OperationType.REFUND,
    # v5.9 特有
    "task": OperationType.EARN,    # v5.9 "task" 视为回收获得
    "bonus": OperationType.EARN,
    "purchase": OperationType.SPEND,
    "redeem": OperationType.SPEND,
    "transfer": OperationType.TRANSFER_OUT,
    "admin_adjust": OperationType.ADJUST,
}


def parse_timestamp(value: str | None) -> datetime | None:
    """解析 v5.9 的多种时间格式。

    v5.9 用了 "2026-04-14 17:26:04"（无时区）和 "2026-05-23T16:19:35.953387" 两种。
    解析失败返回 ``None``（调用方应记录 warning 并用当前时间兜底）。
    """
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    # 常见格式
    fmts = [
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y/%m/%d %H:%M:%S",
    ]
    # 补 +00:00 后缀
    candidate = value
    for fmt in fmts:
        try:
            dt = datetime.strptime(candidate, fmt)  # noqa: DTZ007
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    # ISO format with timezone
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        pass
    return None


def _gen_temp_password() -> str:
    """生成 12 位临时密码（A-Z a-z 0-9）。"""
    alphabet = string.ascii_letters + string.digits
    # 避免易混字符（l / I / 0 / O）
    alphabet = alphabet.translate(str.maketrans("", "", "lIO0o"))
    return "".join(secrets.choice(alphabet) for _ in range(12))


def _is_valid_username(name: str) -> bool:
    return bool(_USERNAME_RE.match(name))


def _coerce_role(value: str | None) -> UserRole:
    """v5.9 role → v2 UserRole。"""
    if not value:
        return UserRole.USER
    s = str(value).strip().lower()
    mapping = {
        "super_admin": UserRole.SUPER_ADMIN,
        "superadmin": UserRole.SUPER_ADMIN,
        "admin": UserRole.ADMIN,
        "operator": UserRole.OPERATOR,
        "user": UserRole.USER,
        "member": UserRole.USER,
    }
    return mapping.get(s, UserRole.USER)


def _load_json(path: Path) -> Any:
    """读 JSON 文件；不存在 / 解析失败返回容错值。"""
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MigrationError(f"无法读取 {path}", details={"path": str(path)}) from exc
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# 用户迁移
# ---------------------------------------------------------------------------
def _migrate_users(
    marks: dict[str, Any] | None,
    *,
    dry_run: bool,
    now: datetime,
    report: MigrationReport,
) -> list[User]:
    """从 marks.json 转 v2 User 列表。

    跳过无效 username、转换 role、生成新密码。
    """
    if not marks or not isinstance(marks, dict):
        report.warnings.append("marks.json 缺失或格式错误：跳过用户迁移")
        return []

    # marks.json 在 v5.9 里既有顶层 dict（username → record），
    # 也有 {"users": {...}, "records": {...}} 嵌套结构；统一处理
    users_map: dict[str, dict[str, Any]]
    if "users" in marks and isinstance(marks["users"], dict):
        users_map = {k: v for k, v in marks["users"].items() if isinstance(v, dict)}
    else:
        users_map = {k: v for k, v in marks.items() if isinstance(v, dict)}

    # 去重（保留第一次出现）
    seen: set[str] = set()
    result: list[User] = []
    for username, raw in users_map.items():
        report.users_total += 1
        if username in seen:
            report.users_skipped += 1
            report.warnings.append(f"重复 username 跳过: {username!r}")
            continue
        seen.add(username)
        if not _is_valid_username(username):
            report.users_failed += 1
            report.errors.append(
                f"username 包含非法字符（v2 不接受）: {username!r}"
            )
            continue
        try:
            user = _convert_user(username, raw, now=now, report=report)
        except Exception as exc:  # noqa: BLE001
            report.users_failed += 1
            report.errors.append(f"用户 {username!r} 转换失败: {exc}")
            continue
        result.append(user)
        report.users_imported += 1
        report.username_to_id[username] = user.id
        if not dry_run:
            report.new_passwords[username] = _gen_temp_password()
    return result


def _convert_user(
    username: str,
    raw: dict[str, Any],
    *,
    now: datetime,
    report: MigrationReport,
) -> User:
    """单条 marks.json 记录 → v2 User。

    密码：v5.9 用 SHA256+salt，v2 用 bcrypt；这里先放合法长度的占位字符串
    （User.password_hash 是 ``str min_length=1``），调用方在持久化前用 bcrypt 重写。
    """
    role = _coerce_role(raw.get("role"))
    points = int(raw.get("points", 0) or 0)
    if points < 0:
        report.warnings.append(f"用户 {username!r} 积分为负 → 归零")
        points = 0
    if points > MAX_AMOUNT:
        report.warnings.append(f"用户 {username!r} 积分超过上限 → 截断")
        points = MAX_AMOUNT

    is_active = not bool(raw.get("disabled", False))
    created_at = parse_timestamp(raw.get("created_at")) or now
    last_login_at = parse_timestamp(raw.get("last_login"))

    # 跳过一些 marks.json 里非用户字段（sentinel keys）
    if not username or not isinstance(username, str):
        raise ValueError("username 为空或类型错误")

    display_name = raw.get("display_name") or username

    return User(
        id=uuid.uuid4().hex,
        username=username,
        display_name=str(display_name)[:64],
        role=role,
        points=points,
        password_hash="placeholder-will-be-overwritten",  # 长度 > 0 满足 min_length=1，调用方在持久化前用 bcrypt 重写
        is_active=is_active,
        is_locked=False,
        failed_login_count=0,
        created_at=created_at,
        updated_at=now,
        last_login_at=last_login_at,
    )


# ---------------------------------------------------------------------------
# 流水迁移
# ---------------------------------------------------------------------------
def _migrate_records(
    history: list[Any] | None,
    username_to_id: dict[str, str],
    *,
    report: MigrationReport,
) -> list[dict[str, Any]]:
    """从 points_history.json 转 v2 PointsRecord 字典列表。"""
    if not history or not isinstance(history, list):
        report.warnings.append("points_history.json 缺失或格式错误：跳过流水迁移")
        return []

    # 用于去重的 set
    seen: set[tuple[str, str, int, str]] = set()
    result: list[dict[str, Any]] = []
    for raw in history:
        report.records_total += 1
        if not isinstance(raw, dict):
            report.records_failed += 1
            report.errors.append("流水记录不是 dict")
            continue
        try:
            record = _convert_record(raw, username_to_id, now=datetime.now(tz=timezone.utc))
        except Exception as exc:  # noqa: BLE001
            report.records_failed += 1
            report.errors.append(f"流水转换失败: {exc}")
            continue
        # 去重键
        key = (
            record["user_id"],
            record["created_at"],
            int(record["amount"]),
            record["reason"],
        )
        if key in seen:
            report.records_skipped += 1
            continue
        seen.add(key)
        result.append(record)
        report.records_imported += 1
    return result


def _convert_record(
    raw: dict[str, Any],
    username_to_id: dict[str, str],
    *,
    now: datetime,
) -> dict[str, Any]:
    username = str(raw.get("username", "")).strip()
    user_id = username_to_id.get(username)
    if user_id is None:
        # 用户没成功导入（中文名等）→ 流水丢弃
        raise ValueError(f"username={username!r} 未导入")

    change = raw.get("change", 0) or 0
    amount = abs(int(change))
    if amount <= 0 or amount > MAX_AMOUNT:
        raise ValueError(f"amount 越界: {amount}")

    op_raw = str(raw.get("operation_type", "")).strip().lower()
    operation = _OPERATION_MAP.get(op_raw, OperationType.ADJUST)

    balance_after = int(raw.get("new_points", 0) or 0)
    if balance_after < 0:
        balance_after = 0
    if balance_after > MAX_AMOUNT:
        balance_after = MAX_AMOUNT

    operator = str(raw.get("operator", "")).strip() or "system"
    operator_id = username_to_id.get(operator) or None

    ts = parse_timestamp(raw.get("timestamp")) or now

    return {
        "id": uuid.uuid4().hex,
        "user_id": user_id,
        "operation": operation.value,
        "amount": amount,
        "balance_after": balance_after,
        "reason": str(raw.get("reason", "") or "")[:500],
        "operator_id": operator_id,
        "created_at": ts.isoformat(),
    }


# ---------------------------------------------------------------------------
# 顶层入口
# ---------------------------------------------------------------------------
def run_migration(
    source: Path,
    target: Path,
    *,
    dry_run: bool = False,
) -> MigrationReport:
    """执行迁移；返回报告。

    :param source: v5.9 数据目录（含 marks.json / points_history.json / ...）
    :param target: v2 数据目录（将写入 users.json / points.json / ...）
    :param dry_run: True 时不写任何文件
    """
    log = get_logger("system")
    report = MigrationReport(dry_run=dry_run)
    now = datetime.now(tz=timezone.utc)

    if not source.exists() or not source.is_dir():
        raise MigrationError(
            f"源目录不存在或不是目录: {source}",
            details={"path": str(source)},
        )

    log.info("迁移开始", source=str(source), target=str(target), dry_run=dry_run)

    # 1) 读 v5.9
    marks = _load_json(source / "marks.json")
    history = _load_json(source / "points_history.json")
    # 暂不使用 audit / notifications（v5.9 是空 list）

    # 2) 用户
    users = _migrate_users(marks, dry_run=dry_run, now=now, report=report)

    # 3) 流水（依赖 username_to_id）
    records = _migrate_records(history, report.username_to_id, report=report)

    # 4) 写目标
    if not dry_run:
        target.mkdir(parents=True, exist_ok=True)
        # 4a) users.json：每个 User 设上新的 bcrypt 密码 + 从 records 算最后余额
        latest_balance = _latest_balances(records)
        for user in users:
            temp_pwd = report.new_passwords.get(user.username, _gen_temp_password())
            user.password_hash = hash_password(temp_pwd)
            report.new_passwords[user.username] = temp_pwd
            if user.id in latest_balance:
                user.points = latest_balance[user.id]
        _write_json(target / "users.json", [u.model_dump(mode="json") for u in users])
        _write_json(target / "points.json", records)
        # audit / notifications 给空 list
        _write_json(target / "audit.json", [])
        _write_json(target / "notifications.json", [])
        log.info(
            "迁移完成（已写入）",
            users=report.users_imported,
            records=report.records_imported,
        )
    else:
        log.info(
            "迁移完成（dry-run，未写文件）",
            users=report.users_imported,
            records=report.records_imported,
        )
    return report


def _latest_balances(records: list[dict[str, Any]]) -> dict[str, int]:
    """从 records 里算每个 user_id 的最新 balance_after。

    策略：取该用户 `created_at` 最大的那条记录的 `balance_after`。
    如果该用户没有 record，返回空（保持 user.points 原样）。
    """
    if not records:
        return {}
    out: dict[str, tuple[str, int]] = {}
    for r in records:
        uid = r.get("user_id")
        if not uid:
            continue
        ts = r.get("created_at") or ""
        cur = out.get(uid)
        if cur is None or ts >= cur[0]:
            out[uid] = (ts, int(r.get("balance_after", 0) or 0))
    return {uid: bal for uid, (_ts, bal) in out.items()}

def _write_json(path: Path, data: Any) -> None:
    """原子写：tmp → rename。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    import os

    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="points_v2-migrate-from-v5_9",
        description="从 v5.9 散落 JSON 迁移到 v2 JsonRepository 格式",
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="v5.9 数据目录（含 marks.json / points_history.json）",
    )
    parser.add_argument(
        "--target",
        type=Path,
        required=True,
        help="v2 数据目录（将写入 users.json / points.json）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="不写任何文件，只生成 report",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="报告输出路径（默认 <target>/migration_report.json，dry-run 必填）",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run_migration(args.source, args.target, dry_run=args.dry_run)
    except MigrationError as exc:
        print(f"[migration] 错误: {exc}", file=sys.stderr)
        return 1

    # 输出报告
    report_path: Path
    if args.report is not None:
        report_path = args.report
    elif args.dry_run:
        # dry-run 强制写到当前目录
        report_path = Path("migration_report.json").resolve()
    else:
        report_path = args.target / "migration_report.json"

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as fh:
        json.dump(report.to_dict(), fh, ensure_ascii=False, indent=2)

    # 控制台简短摘要
    summary = (
        f"[migration] 完成\n"
        f"  users:    total={report.users_total} "
        f"imported={report.users_imported} "
        f"skipped={report.users_skipped} "
        f"failed={report.users_failed}\n"
        f"  records:  total={report.records_total} "
        f"imported={report.records_imported} "
        f"skipped={report.records_skipped} "
        f"failed={report.records_failed}\n"
        f"  dry_run:  {report.dry_run}\n"
        f"  report:   {report_path}\n"
        f"  errors:   {len(report.errors)}  warnings: {len(report.warnings)}"
    )
    print(summary)
    if report.errors:
        print("[migration] 前 10 个错误:", file=sys.stderr)
        for err in report.errors[:10]:
            print(f"  - {err}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
