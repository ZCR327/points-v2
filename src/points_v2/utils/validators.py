"""Input validators (ARCHITECTURE §7).

设计要点
--------

- **业务层 / API 层都用同一组验证函数**——避免重复实现，也方便将来改规则
- 验证失败抛 :class:`ValueError`（API 层会自动转 422）
- 验证通过**返回规范化后的值**（如 username 自动 strip、转小写）
- 校验规则与 ``domain/user.py`` 中的正则保持一致

可配置项
--------
- :func:`configure` 可覆盖 ``password_min_length`` / ``username_min_length``；
  默认从 ``security.password_min_length`` 配置读取
"""

from __future__ import annotations

import re
import threading

from points_v2.core import config

__all__ = [
    "configure",
    "get_password_min_length",
    "validate_username",
    "validate_password_strength",
    "validate_amount",
]

# ---------------------------------------------------------------------------
# 状态（线程安全）
# ---------------------------------------------------------------------------
_lock: threading.RLock = threading.RLock()
_overrides: dict[str, int] = {}


# ---------------------------------------------------------------------------
# 正则常量（与 domain/user.py 保持一致）
# ---------------------------------------------------------------------------
_USERNAME_RE: re.Pattern[str] = re.compile(r"^[A-Za-z0-9_.\-]+$")
_USERNAME_MIN_DEFAULT: int = 3
_USERNAME_MAX: int = 32
_PASSWORD_MIN_DEFAULT: int = 8
_PASSWORD_MAX: int = 128
_AMOUNT_MIN: int = 1
_AMOUNT_MAX: int = 1_000_000_000  # 与 domain/points.MAX_AMOUNT 一致


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
def configure(
    *,
    password_min_length: int | None = None,
    username_min_length: int | None = None,
) -> None:
    """运行时覆盖（**测试用**）。生产配置从 YAML 加载后无需调用。"""
    with _lock:
        if password_min_length is not None:
            _overrides["password_min_length"] = int(password_min_length)
        if username_min_length is not None:
            _overrides["username_min_length"] = int(username_min_length)


def get_password_min_length() -> int:
    """从 overrides 或 config 取密码最小长度（默认 8）。"""
    with _lock:
        if "password_min_length" in _overrides:
            return _overrides["password_min_length"]
    try:
        cfg_value = config.get("security.password_min_length")
    except Exception:  # noqa: BLE001 - 配置未初始化时退默认值
        cfg_value = None
    if isinstance(cfg_value, int) and cfg_value > 0:
        return cfg_value
    return _PASSWORD_MIN_DEFAULT


def _get_username_min() -> int:
    with _lock:
        if "username_min_length" in _overrides:
            return _overrides["username_min_length"]
    return _USERNAME_MIN_DEFAULT


# ---------------------------------------------------------------------------
# 公开验证函数
# ---------------------------------------------------------------------------
def validate_username(value: str) -> str:
    """验证用户名格式。失败抛 :class:`ValueError`；成功返回原值（已 strip）。

    规则：``^[A-Za-z0-9_.-]{3,32}$``
    """
    if not isinstance(value, str):
        raise ValueError("用户名必须是字符串")
    text = value.strip()
    if not text:
        raise ValueError("用户名不能为空")
    if len(text) < _get_username_min():
        raise ValueError(f"用户名长度不能小于 {_get_username_min()} 个字符")
    if len(text) > _USERNAME_MAX:
        raise ValueError(f"用户名长度不能大于 {_USERNAME_MAX} 个字符")
    if not _USERNAME_RE.match(text):
        raise ValueError("用户名只能包含字母、数字、下划线、点、短横线")
    return text


def validate_password_strength(value: str) -> str:
    """验证密码强度。失败抛 :class:`ValueError`；成功返回原值。

    规则：
    - 长度 ≥ :func:`get_password_min_length`（默认 8）
    - 长度 ≤ 128（防止 bcrypt 边界外的滥用）
    - 不限制字符集（学生项目：emoji / 中文都允许）
    """
    if not isinstance(value, str):
        raise ValueError("密码必须是字符串")
    if not value:
        raise ValueError("密码不能为空")
    min_len = get_password_min_length()
    if len(value) < min_len:
        raise ValueError(f"密码长度不能小于 {min_len} 个字符")
    if len(value) > _PASSWORD_MAX:
        raise ValueError(f"密码长度不能大于 {_PASSWORD_MAX} 个字符")
    return value


def validate_amount(value: int) -> int:
    """验证积分数量。失败抛 :class:`ValueError`；成功返回原值。

    规则：``1 <= amount <= 1_000_000_000``
    """
    if isinstance(value, bool):  # bool 是 int 子类；显式排除
        raise ValueError("积分数量必须是整数，不能是布尔值")
    if not isinstance(value, int):
        raise ValueError("积分数量必须是整数")
    if value < _AMOUNT_MIN:
        raise ValueError(f"积分数量不能小于 {_AMOUNT_MIN}")
    if value > _AMOUNT_MAX:
        raise ValueError(f"积分数量不能大于 {_AMOUNT_MAX}")
    return value
