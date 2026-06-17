"""造测试数据脚本（开发 / 演示用）。

用法::

    python scripts/seed_data.py            # 在默认 data/ 目录造数据
    python scripts/seed_data.py --reset    # 先清空 data/ 再造
    python scripts/seed_data.py --users 20 # 自定义用户数（默认 8）

造的数据
--------

- 1 个 super_admin（admin / Admin@123）
- 1 个 admin（operator1 / Oper@123）
- N 个普通用户（user01..userN，密码统一 ``User@123``，含中文名 / 英文名混搭）
- 每个用户预填 0~500 随机积分
- 给每个用户造 3~10 条积分流水（EARN / SPEND / TRANSFER）
- 3 条全局通知
- 1 条审计记录（admin 创建用户的日志）
"""

from __future__ import annotations

import argparse
import random
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 把 src/ 加入 sys.path（standalone 跑）
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="seed_data",
        description="造测试数据（覆盖 data/）",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="造数据前先删除 data/ 下所有 JSON",
    )
    parser.add_argument(
        "--users",
        type=int,
        default=8,
        help="普通用户数（默认 8）",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="随机种子（保证可复现）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    random.seed(args.seed)

    from points_v2.core import paths
    from points_v2.domain.enums import NotificationLevel, OperationType, UserRole
    from points_v2.domain.user import UserCreate
    from points_v2.services import (
        AuditService,
        NotificationService,
        PointsService,
        UserService,
    )
    from points_v2.data import (
        AuditRepository,
        NotificationRepository,
        PointsRepository,
        UserRepository,
    )

    # 1) 路径 / 目录
    paths.setup()
    data_dir = paths.DATA_DIR
    print(f"[seed] data dir: {data_dir}")

    # 2) 可选 reset
    if args.reset:
        for json_file in data_dir.glob("*.json"):
            print(f"[seed] 删除 {json_file.name}")
            json_file.unlink()
        for tmp in data_dir.glob("*.tmp"):
            tmp.unlink()

    # 3) 构造 repo + service
    user_repo = UserRepository()
    points_repo = PointsRepository()
    audit_repo = AuditRepository()
    notification_repo = NotificationRepository()

    user_service = UserService(user_repo=user_repo)
    points_service = PointsService(user_repo=user_repo, points_repo=points_repo)
    audit_service = AuditService(audit_repo=audit_repo)
    notification_service = NotificationService(
        notification_repo=notification_repo,
        user_repo=user_repo,
    )

    # 4) 创建 admin + operator
    print("[seed] 创建 super_admin / admin / 普通用户…")
    super_admin = user_service.create(
        UserCreate(
            username="admin",
            display_name="系统管理员",
            password="Admin@123",
            role=UserRole.SUPER_ADMIN,
            initial_points=0,
        ),
    )
    operator = user_service.create(
        UserCreate(
            username="operator1",
            display_name="运营",
            password="Oper@123",
            role=UserRole.OPERATOR,
            initial_points=50,
        ),
    )

    # 5) 普通用户
    user_pool: list[tuple[str, str]] = [
        ("alice", "爱丽丝"),
        ("bob", "鲍勃"),
        ("carol", "卡萝"),
        ("dave", "戴夫"),
        ("eve", "伊芙"),
        ("frank", "法兰克"),
        ("grace", "格蕾丝"),
        ("henry", "亨利"),
        ("ivy", "艾薇"),
        ("jack", "杰克"),
    ]
    created_users = [super_admin, operator]
    for i in range(min(args.users, len(user_pool))):
        uname, dname = user_pool[i]
        initial = random.randint(0, 500)
        try:
            u = user_service.create(
                UserCreate(
                    username=uname,
                    display_name=dname,
                    password="User@123",
                    role=UserRole.USER,
                    initial_points=initial,
                ),
            )
            created_users.append(u)
        except Exception as exc:  # noqa: BLE001 - 已存在时跳过
            print(f"[seed] 跳过 {uname}: {exc}")

    # 6) 给每个用户造流水
    print(f"[seed] 给 {len(created_users)} 个用户造流水…")
    now = datetime.now(tz=timezone.utc)
    for u in created_users:
        record_count = random.randint(3, 10)
        for k in range(record_count):
            op = random.choice(
                [OperationType.EARN, OperationType.EARN, OperationType.SPEND, OperationType.SPEND, OperationType.ADJUST],
            )
            amount = random.randint(1, 80)
            if op == OperationType.SPEND and u.points < amount:
                continue
            try:
                ts = now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
                # 简化：直接 add / deduct（不严格按时间倒序）
                if op == OperationType.EARN:
                    points_service.add(u.id, amount, reason=f"回收 {random.choice(['纸板', '塑料', '金属'])}", operator_id=operator.id)
                elif op == OperationType.SPEND:
                    points_service.deduct(u.id, amount, reason=f"兑换 {random.choice(['文具', '零食', '饮料'])}", operator_id=operator.id)
                elif op == OperationType.ADJUST:
                    points_service.add(u.id, amount, reason="管理员手动调整", operator_id=super_admin.id)
            except Exception as exc:  # noqa: BLE001
                print(f"[seed]   {u.username} 流水失败: {exc}")

    # 7) 通知
    print("[seed] 创建通知…")
    notification_service.create(
        NotificationLevel.INFO,
        "欢迎使用积分系统 v2",
        "v2 桌面端已上线，登录后请尽快修改默认密码。",
    )
    notification_service.create(
        NotificationLevel.WARNING,
        "数据备份",
        "建议每周手动备份 data/ 目录。",
    )
    notification_service.create(
        NotificationLevel.ERROR,
        "测试错误通知",
        "这是一条演示错误通知，可忽略。",
        user_id=operator.id,
    )

    # 8) 审计
    print("[seed] 写入审计…")
    audit_service.log(
        "system.seed",
        user_id=super_admin.id,
        details={"users_created": len(created_users), "seed_script": True},
    )

    # 9) 汇总
    print(
        f"[seed] 完成！用户={len(created_users)} 流水={len(points_repo.all())} "
        f"通知={len(notification_repo.all())}"
    )
    print(f"[seed] 默认账号：admin / Admin@123（super_admin）")
    print(f"[seed] 默认账号：operator1 / Oper@123（operator）")
    print(f"[seed] 默认账号：alice / User@123（user，仅在 --users ≥ 1 时存在）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
