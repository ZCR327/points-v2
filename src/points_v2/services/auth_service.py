"""AuthService — login / logout / verify_token / change_password.

设计要点
--------

- **token =** ``secrets.token_urlsafe(32)`` 随机 43 字符串
- token → user_id 映射存 ``data/sessions.json``（**独立文件**，与其他数据隔离）
- 业务规则：
  - 登录失败计数 + 锁定（达到 ``security.max_failed_logins`` 自动 lock）
  - 锁定 / 禁用用户无法登录
  - 登录成功后清零失败计数 + 更新 ``last_login_at``
- 不直接调其他 service（避免循环依赖）；由 :class:`Container` 注入

依赖
----
- :class:`points_v2.data.user_repo.UserRepository`
- :class:`points_v2.data.audit_repo.AuditRepository` （可选）
"""

from __future__ import annotations

import json
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from points_v2.core import config, paths
from points_v2.core.exceptions import (
    AuthError,
    InvalidCredentialsError,
    UserNotFoundError,
)
from points_v2.core.logging import get_logger
from points_v2.domain.enums import UserRole
from points_v2.domain.user import User
from points_v2.utils.hashing import hash_password, verify_password
from points_v2.utils.time import utcnow

if TYPE_CHECKING:
    from points_v2.data.audit_repo import AuditRepository
    from points_v2.data.user_repo import UserRepository

__all__ = ["AuthService", "AuthToken"]


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AuthToken:
    """API 认证 token。

    - ``token``: 43 字符串（``secrets.token_urlsafe(32)``）
    - ``user_id``: 关联用户
    - ``expires_at``: 过期时间（UTC）
    - ``role`` / ``username``: 方便 API 端直接读，避免每次查 repo
    """

    token: str
    user_id: str
    username: str
    role: UserRole
    expires_at: datetime


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class AuthService:
    """认证服务：登录 / 登出 / 校验 token / 改密。"""

    SESSIONS_FILENAME: str = "sessions.json"

    def __init__(
        self,
        user_repo: UserRepository,
        audit_repo: AuditRepository | None = None,
        *,
        base_dir: Path | None = None,
        session_ttl_hours: int | None = None,
        max_failed_logins: int | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._audit_repo = audit_repo
        self._base_dir: Path = base_dir or paths.DATA_DIR
        self._file: Path = self._base_dir / self.SESSIONS_FILENAME
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock: threading.RLock = threading.RLock()
        self._loaded: bool = False
        # 配置项：允许在构造时覆盖（测试）
        self._session_ttl_hours = session_ttl_hours or self._read_ttl()
        self._max_failed_logins = max_failed_logins or self._read_max_failed()

    # ------------------------------------------------------------------ 公共
    def login(
        self,
        username: str,
        password: str,
        *,
        ip_address: str | None = None,
    ) -> AuthToken:
        """登录；返回 token。失败抛 :class:`InvalidCredentialsError` 或 :class:`AuthError`。"""
        log = get_logger("login")
        user = self._user_repo.get_by_username(username)
        if user is None:
            log.info("登录失败: 用户不存在", user=username, ip=ip_address)
            self._audit("user.login_fail", None, username, {"reason": "no_user"}, ip_address)
            raise InvalidCredentialsError("用户名或密码错误")

        if not user.is_active:
            self._audit("user.login_fail", user.id, username, {"reason": "inactive"}, ip_address)
            raise AuthError("账户已停用", details={"user_id": user.id})

        if user.is_locked:
            self._audit("user.login_fail", user.id, username, {"reason": "locked"}, ip_address)
            raise AuthError("账户已锁定", details={"user_id": user.id})

        if not verify_password(password, user.password_hash):
            # 增加失败计数；超限 → 自动 lock
            new_count = user.failed_login_count + 1
            should_lock = new_count >= self._max_failed_logins
            updated = user.model_copy(
                update={
                    "failed_login_count": new_count,
                    "is_locked": should_lock or user.is_locked,
                },
            )
            updated.touch()
            self._user_repo.update(updated)
            log.info(
                "登录失败: 密码错误",
                user=username,
                failed_count=new_count,
                locked=should_lock,
                ip=ip_address,
            )
            self._audit(
                "user.login_fail",
                user.id,
                username,
                {"reason": "bad_password", "failed_count": new_count, "locked": should_lock},
                ip_address,
            )
            raise InvalidCredentialsError("用户名或密码错误")

        # 成功：清零失败计数 + 更新 last_login_at + 颁发 token
        now = utcnow()
        refreshed = user.model_copy(
            update={
                "failed_login_count": 0,
                "is_locked": False,
                "last_login_at": now,
            },
        )
        refreshed.touch()
        self._user_repo.update(refreshed)

        token_str = secrets.token_urlsafe(32)
        expires_at = now + timedelta(hours=self._session_ttl_hours)
        record = {
            "token": token_str,
            "user_id": user.id,
            "username": user.username,
            "role": user.role.value,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        with self._lock:
            self._ensure_loaded()
            self._sessions[token_str] = record
            self._persist()

        log.info("登录成功", user=username, user_id=user.id, ip=ip_address)
        self._audit("user.login", user.id, username, None, ip_address)

        return AuthToken(
            token=token_str,
            user_id=user.id,
            username=user.username,
            role=user.role,
            expires_at=expires_at,
        )

    def logout(self, token: str) -> bool:
        """登出：删除 token。返回是否真的删了。"""
        with self._lock:
            self._ensure_loaded()
            if token in self._sessions:
                record = self._sessions.pop(token)
                self._persist()
                self._audit("user.logout", record["user_id"], record["username"], None, None)
                return True
            return False

    def verify_token(self, token: str) -> User:
        """校验 token 有效性；返回对应 :class:`User`。

        - token 不存在 / 已过期 → :class:`AuthError`
        - 关联用户被删 / 禁用 → :class:`AuthError`
        """
        with self._lock:
            self._ensure_loaded()
            record = self._sessions.get(token)
            if record is None:
                raise InvalidCredentialsError("token 无效或已过期")
            expires_at = datetime.fromisoformat(record["expires_at"])
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= utcnow():
                # 顺手清掉过期 token
                del self._sessions[token]
                self._persist()
                raise InvalidCredentialsError("token 已过期")

        user = self._user_repo.get(record["user_id"])
        if user is None:
            # 关联用户被删 → 清 token
            with self._lock:
                self._sessions.pop(token, None)
                self._persist()
            raise UserNotFoundError("token 关联用户不存在")
        if not user.is_active or user.is_locked:
            raise AuthError("用户已被禁用或锁定", details={"user_id": user.id})
        return user

    def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str,
    ) -> None:
        """修改密码（需要旧密码验证）。失败抛 :class:`AuthError`。

        修改成功后**吊销该用户所有现存 token**（强制重新登录）。
        """
        user = self._user_repo.get(user_id)
        if user is None:
            raise UserNotFoundError(f"用户 {user_id} 不存在")
        if not verify_password(old_password, user.password_hash):
            raise InvalidCredentialsError("旧密码错误")
        if old_password == new_password:
            raise AuthError("新密码不能与旧密码相同")
        new_hash = hash_password(new_password)
        updated = user.model_copy(update={"password_hash": new_hash, "failed_login_count": 0})
        updated.touch()
        self._user_repo.update(updated)
        # 吊销所有 token
        self.revoke_all_for_user(user_id)
        self._audit("user.change_password", user_id, user.username, None, None)

    def revoke_all_for_user(self, user_id: str) -> int:
        """吊销某用户的所有 token；返回数量。**供 admin 强制下线**。"""
        with self._lock:
            self._ensure_loaded()
            to_remove = [t for t, r in self._sessions.items() if r["user_id"] == user_id]
            for t in to_remove:
                del self._sessions[t]
            if to_remove:
                self._persist()
            return len(to_remove)

    def active_session_count(self) -> int:
        """返回当前有效会话数（含过期但未清理的）。"""
        with self._lock:
            self._ensure_loaded()
            return len(self._sessions)

    def cleanup_expired(self) -> int:
        """清理过期 token；返回数量。**可定期调用**。"""
        now = utcnow()
        with self._lock:
            self._ensure_loaded()
            expired: list[str] = []
            for token, record in self._sessions.items():
                exp = datetime.fromisoformat(record["expires_at"])
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if exp <= now:
                    expired.append(token)
            for token in expired:
                del self._sessions[token]
            if expired:
                self._persist()
            return len(expired)

    # ------------------------------------------------------------------ 内部
    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._load()

    def _load(self) -> None:
        with self._lock:
            if self._loaded:
                return
            if not self._file.exists():
                self._sessions = {}
                self._loaded = True
                return
            try:
                raw = self._file.read_text(encoding="utf-8")
            except OSError:
                self._sessions = {}
                self._loaded = True
                return
            if not raw.strip():
                self._sessions = {}
                self._loaded = True
                return
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                # 损坏的 sessions 文件 → 当空文件处理（容错）
                self._sessions = {}
                self._loaded = True
                return
            if isinstance(data, list):
                # 兼容旧的 list 格式（不应出现，但稳妥处理）
                self._sessions = {}
            elif isinstance(data, dict):
                self._sessions = {str(k): dict(v) for k, v in data.items()}
            else:
                self._sessions = {}
            self._loaded = True

    def _persist(self) -> None:
        """原子写：先 tmp 后 rename。"""
        self._base_dir.mkdir(parents=True, exist_ok=True)
        tmp = self._file.with_suffix(self._file.suffix + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(self._sessions, fh, ensure_ascii=False, indent=2)
            import os

            os.replace(tmp, self._file)
        except OSError:
            # 失败不应阻断业务；下次启动会自动重建
            pass
        finally:
            with __import__("contextlib").suppress(OSError):
                if tmp.exists():
                    tmp.unlink()

    def _audit(
        self,
        action: str,
        user_id: str | None,
        resource: str | None,
        details: dict[str, Any] | None,
        ip_address: str | None,
    ) -> None:
        if self._audit_repo is None:
            return
        try:
            from points_v2.domain.audit import AuditLog  # noqa: PLC0415

            log = AuditLog(
                user_id=user_id,
                action=action,
                resource=resource,
                details=details or {},
                ip_address=ip_address,
            )
            self._audit_repo.insert(log)
        except Exception:  # noqa: BLE001 - 审计失败不影响主流程
            pass

    def _read_ttl(self) -> int:
        try:
            value = config.get("security.session_ttl_hours")
            if isinstance(value, int) and value > 0:
                return value
        except Exception:  # noqa: BLE001
            pass
        return 24

    def _read_max_failed(self) -> int:
        try:
            value = config.get("security.max_failed_logins")
            if isinstance(value, int) and value > 0:
                return value
        except Exception:  # noqa: BLE001
            pass
        return 5
