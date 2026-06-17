"""End-to-end tests for the FastAPI HTTP API (FastAPI TestClient + httpx).

设计要点
--------

- 每个测试构造独立的 ``app``（传自定义 service bundle 隔离数据）
- 用 ``fastapi.testclient.TestClient`` 驱动 app —— 不开真实端口（CI 友好）
- 不依赖真实时间（不需要 freezegun 之类）
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from points_v2.api.app import create_app
from points_v2.api.app_state import ServiceBundle, build_default_services
from points_v2.domain.enums import UserRole
from points_v2.domain.user import UserCreate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def services(tmp_data_dir) -> ServiceBundle:
    """默认 services 集合；带一个 admin + 一个普通 user。"""
    bundle = build_default_services()
    bundle.user_service.create(
        UserCreate(
            username="admin1",
            display_name="Admin",
            password="AdminPass123",
            role=UserRole.ADMIN,
            initial_points=0,
        ),
    )
    bundle.user_service.create(
        UserCreate(
            username="alice",
            display_name="Alice",
            password="AlicePass123",
            role=UserRole.USER,
            initial_points=100,
        ),
    )
    bundle.user_service.create(
        UserCreate(
            username="bob",
            display_name="Bob",
            password="BobPass123",
            role=UserRole.USER,
            initial_points=0,
        ),
    )
    return bundle


@pytest.fixture
def client(services: ServiceBundle) -> Iterator[TestClient]:
    """FastAPI TestClient（基于 httpx，sync API）。"""
    app = create_app(services=services)
    with TestClient(app) as c:
        yield c


def _login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 11 个测试（≥10）
# ---------------------------------------------------------------------------
def test_health_returns_ok(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_login_success_and_me(client: TestClient) -> None:
    token = _login(client, "alice", "AlicePass123")
    r = client.get("/api/auth/me", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "alice"
    assert body["role"] == "user"
    assert body["points"] == 100


def test_login_wrong_password_returns_401(client: TestClient) -> None:
    r = client.post("/api/auth/login", json={"username": "alice", "password": "bad"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_missing_token_returns_401(client: TestClient) -> None:
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_logout_invalidates_token(client: TestClient) -> None:
    token = _login(client, "alice", "AlicePass123")
    r = client.post("/api/auth/logout", headers=_auth(token))
    assert r.status_code == 200
    # 再访问 me → 401
    r2 = client.get("/api/auth/me", headers=_auth(token))
    assert r2.status_code == 401


def test_admin_create_user_then_list(client: TestClient) -> None:
    token = _login(client, "admin1", "AdminPass123")
    r = client.post(
        "/api/users",
        json={
            "username": "carol",
            "display_name": "Carol",
            "password": "CarolPass123",
            "role": "user",
            "initial_points": 10,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201
    created = r.json()
    assert created["username"] == "carol"
    assert created["points"] == 10

    # 普通用户不能创建
    user_token = _login(client, "alice", "AlicePass123")
    r2 = client.post(
        "/api/users",
        json={
            "username": "dave",
            "display_name": "Dave",
            "password": "DavePass123",
            "role": "user",
        },
        headers=_auth(user_token),
    )
    assert r2.status_code == 403

    # 列出
    r3 = client.get("/api/users", headers=_auth(token))
    assert r3.status_code == 200
    usernames = [u["username"] for u in r3.json()]
    assert {"admin1", "alice", "bob", "carol"} <= set(usernames)


def test_points_add_and_deduct_balance_and_history(client: TestClient) -> None:
    admin_token = _login(client, "admin1", "AdminPass123")
    user_token = _login(client, "alice", "AlicePass123")
    alice_id = _me(client, user_token)
    # alice 当前 100，加 50
    r = client.post(
        "/api/points/add",
        json={"user_id": alice_id, "amount": 50, "reason": "回收"},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200
    assert r.json()["balance_after"] == 150

    # 查余额
    r2 = client.get(f"/api/users/{alice_id}/points", headers=_auth(user_token))
    assert r2.status_code == 200
    assert r2.json()["points"] == 150

    # 扣 30
    r3 = client.post(
        "/api/points/deduct",
        json={"user_id": alice_id, "amount": 30, "reason": "商城"},
        headers=_auth(admin_token),
    )
    assert r3.status_code == 200
    assert r3.json()["balance_after"] == 120

    # 历史（应有 2 条）
    r4 = client.get(
        f"/api/users/{alice_id}/points/history?days=1&limit=10",
        headers=_auth(user_token),
    )
    assert r4.status_code == 200
    assert r4.json()["total"] == 2


def test_points_deduct_insufficient_returns_409(client: TestClient) -> None:
    admin_token = _login(client, "admin1", "AdminPass123")
    bob_id = _get_user_id_by_username(client, admin_token, "bob")
    # bob 当前 0
    r = client.post(
        "/api/points/deduct",
        json={"user_id": bob_id, "amount": 10, "reason": "bad"},
        headers=_auth(admin_token),
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INSUFFICIENT_POINTS"


def test_transfer_between_users(client: TestClient) -> None:
    admin_token = _login(client, "admin1", "AdminPass123")
    alice_id = _get_user_id_by_username(client, admin_token, "alice")
    bob_id = _get_user_id_by_username(client, admin_token, "bob")
    r = client.post(
        "/api/points/transfer",
        json={
            "fromUserId": alice_id,
            "toUserId": bob_id,
            "amount": 40,
            "reason": "gift",
        },
        headers=_auth(admin_token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    # alice 100 → 60，bob 0 → 40
    alice_now = client.get(
        f"/api/users/{alice_id}/points", headers=_auth(admin_token)
    ).json()["points"]
    bob_now = client.get(
        f"/api/users/{bob_id}/points", headers=_auth(admin_token)
    ).json()["points"]
    assert (alice_now, bob_now) == (60, 40)


def test_admin_endpoints_require_admin_role(client: TestClient) -> None:
    """非 admin 访问 /api/admin/* → 403。"""
    user_token = _login(client, "alice", "AlicePass123")
    r = client.get("/api/admin/stats", headers=_auth(user_token))
    assert r.status_code == 403
    r2 = client.get("/api/admin/rankings", headers=_auth(user_token))
    assert r2.status_code == 403
    r3 = client.get("/api/admin/audit", headers=_auth(user_token))
    assert r3.status_code == 403


def test_notifications_create_and_list_and_mark_read(client: TestClient) -> None:
    """admin 发通知，alice 看通知并标记已读。"""
    admin_token = _login(client, "admin1", "AdminPass123")
    alice_token = _login(client, "alice", "AlicePass123")
    # 全局广播
    r = client.post(
        "/api/admin/notifications",
        json={
            "level": "info",
            "title": "系统通知",
            "content": "v2 上线",
            "user_id": None,
        },
        headers=_auth(admin_token),
    )
    assert r.status_code == 200
    nid = r.json()["id"]

    # alice 看到通知
    r2 = client.get("/api/admin/notifications", headers=_auth(alice_token))
    assert r2.status_code == 200
    items = r2.json()["items"]
    assert any(n["id"] == nid and not n["is_read"] for n in items)

    # 标记已读
    r3 = client.post(
        f"/api/admin/notifications/{nid}/read", headers=_auth(alice_token)
    )
    assert r3.status_code == 200

    # 复查
    r4 = client.get(
        "/api/admin/notifications?unread_only=true",
        headers=_auth(alice_token),
    )
    assert r4.status_code == 200
    assert all(n["is_read"] for n in r4.json()["items"])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _me(client: TestClient, token: str) -> str:
    """取当前用户 id。"""
    r = client.get("/api/auth/me", headers=_auth(token))
    assert r.status_code == 200
    return r.json()["id"]


def _get_user_id_by_username(client: TestClient, admin_token: str, username: str) -> str:
    r = client.get("/api/users?limit=500", headers=_auth(admin_token))
    assert r.status_code == 200
    for u in r.json():
        if u["username"] == username:
            return u["id"]
    raise AssertionError(f"user {username!r} not found")
