"""Custom exception hierarchy for the points_v2 application.

设计要点
--------

- 所有异常继承自 :class:`PointsV2Error`（再继承自 ``Exception``），便于在最外层用
  ``except PointsV2Error`` 一网打尽业务异常，与系统异常（OSError、ValueError）分层。
- 业务异常**不携带** HTTP 状态码——那是 api/ 层的关注点；业务层只表达"出了什么
  事"，怎么呈现由调用方决定。
- 中文 ``message`` 字段可让 UI 层直接显示，无需翻译。
- 任何异常都可以携带 ``details: dict`` 用于调试上下文（不打印到生产 UI）。

设计契约（ARCHITECTURE §4.2）
-----------------------------
异常树（部分）::

    PointsV2Error
    ├── AuthError
    │   └── InvalidCredentialsError
    ├── InsufficientPointsError
    ├── UserNotFoundError
    ├── DuplicateUserError
    ├── ConfigError
    ├── StorageError
    └── MigrationError
"""

from __future__ import annotations

from typing import Any


class PointsV2Error(Exception):
    """所有业务异常的基类。

    :param message: 人类可读的中文错误描述（用于 UI / 日志）。
    :param details: 任意调试上下文（API 层会原样放进响应体）。
    """

    def __init__(self, message: str = "", *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message: str = message
        self.details: dict[str, Any] = details or {}

    def __str__(self) -> str:  # pragma: no cover - 简单透传
        if self.details:
            return f"{self.message} (details={self.details})"
        return self.message


# ---------------------------------------------------------------------------
# 认证 / 鉴权
# ---------------------------------------------------------------------------
class AuthError(PointsV2Error):
    """认证 / 鉴权失败基类（如 token 无效、权限不足）。"""


class InvalidCredentialsError(AuthError):
    """用户名 / 密码不匹配，或 token 已过期。"""


# ---------------------------------------------------------------------------
# 积分 / 用户业务规则
# ---------------------------------------------------------------------------
class InsufficientPointsError(PointsV2Error):
    """用户积分不足以完成扣减 / 转账。"""

    def __init__(
        self,
        message: str = "积分不足",
        *,
        balance: int = 0,
        required: int = 0,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged: dict[str, Any] = {"balance": balance, "required": required}
        if details:
            merged.update(details)
        super().__init__(message, details=merged)


class UserNotFoundError(PointsV2Error):
    """根据 id / username 找不到用户。"""


class DuplicateUserError(PointsV2Error):
    """创建用户时用户名 / 邮箱等唯一字段重复。"""


# ---------------------------------------------------------------------------
# 基础设施
# ---------------------------------------------------------------------------
class ConfigError(PointsV2Error):
    """配置文件缺失 / 解析失败 / 关键字段缺失。"""


class StorageError(PointsV2Error):
    """数据存取失败（文件 IO 错误、JSON 损坏、并发冲突）。"""


class MigrationError(PointsV2Error):
    """数据迁移过程中出现不可恢复错误。"""


__all__ = [
    "PointsV2Error",
    "AuthError",
    "InvalidCredentialsError",
    "InsufficientPointsError",
    "UserNotFoundError",
    "DuplicateUserError",
    "ConfigError",
    "StorageError",
    "MigrationError",
]
