"""Tests for points_v2.domain.user."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from points_v2.domain.enums import UserRole
from points_v2.domain.user import UserCreate, UserUpdate


def test_user_create_minimal() -> None:
    """最小有效输入：username + display_name + password。"""
    payload = UserCreate(
        username="alice",
        display_name="Alice",
        password="hunter2hunter",
    )
    assert payload.username == "alice"
    assert payload.role is UserRole.USER
    assert payload.initial_points == 0


def test_user_username_validator_rejects_bad_chars() -> None:
    """含特殊字符的用户名应被拒。"""
    with pytest.raises(ValidationError):
        UserCreate(username="bad name!", display_name="x", password="longenough1")


def test_user_password_too_short() -> None:
    """密码 < 8 字符应被拒。"""
    with pytest.raises(ValidationError):
        UserCreate(username="alice", display_name="Alice", password="short")


def test_user_extra_forbidden() -> None:
    """``extra="forbid"``：未声明字段抛错。"""
    with pytest.raises(ValidationError):
        UserCreate(
            username="alice",
            display_name="Alice",
            password="longenough1",
            extra_field="oops",  # type: ignore[call-arg]
        )


def test_user_update_has_any() -> None:
    """``UserUpdate.has_any()`` 反映是否真的有字段需要更新。"""
    empty = UserUpdate()
    assert empty.has_any() is False
    partial = UserUpdate(display_name="New")
    assert partial.has_any() is True
    role_only = UserUpdate(role=UserRole.ADMIN)
    assert role_only.has_any() is True
