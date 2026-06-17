"""Password hashing helpers (bcrypt, ARCHITECTURE §5.1).

设计要点
--------

- 使用 **bcrypt**（学生项目够用；将来要换 argon2/scrypt 只要改本文件）
- 内部统一调用 :func:`hash_password` / :func:`verify_password`；业务层不要直接 import ``bcrypt``
- salt 是自动生成；同一明文多次哈希结果不同——这是预期行为
- ``verify_password`` 在哈希不合法时返回 ``False``（不抛）——避免存储脏数据导致登录崩溃

安全注意
--------
- 永远不要 ``print(echo)`` 或 log 明文密码
- 日志中只记 ``user_id``，不记 password / hash
- ``bcrypt`` 默认 cost=12（约 250ms）；测试可调小但生产不动
"""

from __future__ import annotations

import bcrypt

# 业务层不直接 import bcrypt；通过这两个函数屏蔽细节
__all__ = ["hash_password", "verify_password"]


def hash_password(plain: str) -> str:
    """把明文密码哈希成 bcrypt 字符串（**包含 salt**）。

    :param plain: 明文密码；空串抛 :class:`ValueError`。
    :returns: ``$2b$12$...`` 形式的字符串，存进 ``User.password_hash``。
    """
    if not isinstance(plain, str) or not plain:
        raise ValueError("hash_password: 明文密码必须是非空字符串")
    # bcrypt 限制：明文最长 72 字节；超出截断（与现有系统行为一致）
    encoded = plain.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    hashed: bytes = bcrypt.hashpw(encoded, salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """验证明文密码与哈希是否匹配。

    - 哈希格式错误 / 算法不识别 → 返回 ``False``（**不抛异常**）
    - 空字符串哈希（如 ``""`` / ``None``）→ ``False``

    :returns: ``True`` 当且仅当 ``plain`` 与 ``hashed`` 匹配。
    """
    if not plain or not hashed:
        return False
    try:
        encoded = plain.encode("utf-8")[:72]
        # bcrypt.checkpw 接受 str 或 bytes；统一转 bytes
        return bcrypt.checkpw(encoded, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        # 哈希格式损坏（不是 $2b$ 开头等）
        return False
