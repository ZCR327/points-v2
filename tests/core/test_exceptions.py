"""Tests for points_v2.core.exceptions."""

from __future__ import annotations

from points_v2.core.exceptions import (
    AuthError,
    ConfigError,
    DuplicateUserError,
    InsufficientPointsError,
    InvalidCredentialsError,
    MigrationError,
    PointsV2Error,
    StorageError,
    UserNotFoundError,
)


def test_inheritance_chain() -> None:
    """所有业务异常应继承自 :class:`PointsV2Error`，``InvalidCredentialsError`` 还应继承 AuthError。"""
    assert issubclass(AuthError, PointsV2Error)
    assert issubclass(InvalidCredentialsError, AuthError)
    assert issubclass(InvalidCredentialsError, PointsV2Error)
    assert issubclass(InsufficientPointsError, PointsV2Error)
    assert issubclass(UserNotFoundError, PointsV2Error)
    assert issubclass(DuplicateUserError, PointsV2Error)
    assert issubclass(ConfigError, PointsV2Error)
    assert issubclass(StorageError, PointsV2Error)
    assert issubclass(MigrationError, PointsV2Error)


def test_points_v2_error_carries_details() -> None:
    """``details`` 应被存储；``str()`` 反映 message。"""
    err = PointsV2Error("oops", details={"x": 1})
    assert err.message == "oops"
    assert err.details == {"x": 1}
    assert "oops" in str(err)
    # 无 details 时不带括号
    err2 = PointsV2Error("plain")
    assert "details" not in str(err2)


def test_insufficient_points_exposes_balance_and_required() -> None:
    """专用字段 ``balance`` / ``required`` 应被合并进 ``details``。"""
    err = InsufficientPointsError("积分不足", balance=10, required=50)
    assert err.details["balance"] == 10
    assert err.details["required"] == 50
    # 可继续追加 details 不被覆盖专用字段
    err2 = InsufficientPointsError(balance=0, required=1, details={"user": "alice"})
    assert err2.details["balance"] == 0
    assert err2.details["required"] == 1
    assert err2.details["user"] == "alice"
