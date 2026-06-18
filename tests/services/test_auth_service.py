"""Tests for AuthService (login / logout / verify_token / change_password)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from points_v2.core.exceptions import (
    AuthError,
    InvalidCredentialsError,
)
from points_v2.data.audit_repo import AuditRepository
from points_v2.data.user_repo import UserRepository
from points_v2.domain.enums import UserRole
from points_v2.domain.user import UserCreate
from points_v2.services.auth_service import AuthService


def _build_service(tmp_data_dir, max_failed: int = 5, ttl_hours: int = 24):
    user_repo = UserRepository()
    audit_repo = AuditRepository()
    auth = AuthService(
        user_repo=user_repo,
        audit_repo=audit_repo,
        max_failed_logins=max_failed,
        session_ttl_hours=ttl_hours,
    )
    user_svc = __import__("points_v2.services.user_service", fromlist=["UserService"]).UserService(
        user_repo,
    )
    return auth, user_svc, user_repo, audit_repo


def _make_user(user_service, username: str, password: str = "TestPass123", role=UserRole.USER):
    return user_service.create(
        UserCreate(
            username=username,
            display_name=username.title(),
            password=password,
            role=role,
            initial_points=100,
        ),
    )


# ---------------------------------------------------------------------------
# 6 个测试
# ---------------------------------------------------------------------------
def test_login_success_returns_token(tmp_data_dir) -> None:
    """登录成功返回带 token / 过期时间的 AuthToken。"""
    auth, user_svc, _, _ = _build_service(tmp_data_dir)
    _make_user(user_svc, "alice", password="TestPass123")
    token = auth.login("alice", "TestPass123")
    assert token.token
    assert len(token.token) >= 32
    assert token.username == "alice"
    assert token.role is UserRole.USER
    assert token.expires_at > datetime.now(tz=timezone.utc)


def test_login_wrong_password_raises_and_increments_counter(tmp_data_dir) -> None:
    """密码错 → InvalidCredentialsError，失败计数 +1。"""
    auth, user_svc, user_repo, _ = _build_service(tmp_data_dir, max_failed=3)
    user = _make_user(user_svc, "alice")
    assert user.failed_login_count == 0
    with pytest.raises(InvalidCredentialsError):
        auth.login("alice", "wrong")
    refreshed = user_repo.get(user.id)
    assert refreshed.failed_login_count == 1
    assert refreshed.is_locked is False


def test_login_locks_after_max_failures(tmp_data_dir) -> None:
    """失败次数达到上限自动 lock。"""
    auth, user_svc, user_repo, _ = _build_service(tmp_data_dir, max_failed=3)
    user = _make_user(user_svc, "alice")
    for _ in range(3):
        with pytest.raises(InvalidCredentialsError):
            auth.login("alice", "wrong")
    # 第 4 次：账户已 lock → AuthError
    with pytest.raises(AuthError, match="锁定"):
        auth.login("alice", "TestPass123")
    assert user_repo.get(user.id).is_locked is True


def test_logout_invalidates_token(tmp_data_dir) -> None:
    """logout 后 verify_token 失败。"""
    auth, user_svc, _, _ = _build_service(tmp_data_dir)
    _make_user(user_svc, "alice")
    token = auth.login("alice", "TestPass123")
    # 校验成功
    user = auth.verify_token(token.token)
    assert user.username == "alice"
    assert auth.logout(token.token) is True
    # 注销后失效
    with pytest.raises(InvalidCredentialsError):
        auth.verify_token(token.token)
    # 重复 logout 返回 False
    assert auth.logout(token.token) is False


def test_verify_token_rejects_expired(tmp_data_dir) -> None:
    """token 过期 → InvalidCredentialsError。"""
    auth, user_svc, _, _ = _build_service(tmp_data_dir, ttl_hours=0)
    # ttl=0 + 创建后手动把过期时间改到过去
    _make_user(user_svc, "alice")
    token = auth.login("alice", "TestPass123")
    # 手动篡改 sessions.json 中的 expires_at
    with auth._lock:  # type: ignore[attr-defined]
        auth._sessions[token.token]["expires_at"] = (  # type: ignore[attr-defined]
            datetime.now(tz=timezone.utc) - timedelta(hours=1)
        ).isoformat()
        auth._persist()  # type: ignore[attr-defined]
    with pytest.raises(InvalidCredentialsError, match="过期"):
        auth.verify_token(token.token)


def test_change_password_revokes_all_tokens(tmp_data_dir) -> None:
    """改密成功后吊销该用户所有 token。"""
    auth, user_svc, user_repo, _ = _build_service(tmp_data_dir)
    user = _make_user(user_svc, "alice", password="OldPass123")
    old_token = auth.login("alice", "OldPass123")
    assert auth.active_session_count() >= 1
    # 改密
    auth.change_password(user.id, "OldPass123", "NewPass456")
    # 旧 token 失效
    with pytest.raises(InvalidCredentialsError):
        auth.verify_token(old_token.token)
    # 新密码可登录
    new_token = auth.login("alice", "NewPass456")
    user_after = user_repo.get(user.id)
    assert user_after.password_hash != user.password_hash
    # 新 token 可校验
    assert auth.verify_token(new_token.token).id == user.id
