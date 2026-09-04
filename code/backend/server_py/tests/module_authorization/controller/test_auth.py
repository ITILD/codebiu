# -*- coding: utf-8 -*-
"""module_authorization/auth 接口标准测试
覆盖: 登录/OAuth2登录/注册/me/me-id/me-permissions/刷新/登出/401场景
"""

import time
import uuid

import httpx

BASE = "/authorization/auth"


async def test_login_ok(client: httpx.AsyncClient):
    """管理员正常登录,返回双令牌与用户信息"""
    resp = await client.post(
        f"{BASE}/login", data={"username": "admin", "password": "admin123"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tokens"]["access"]["token"], "应返回访问令牌"
    assert body["tokens"]["refresh"]["token"], "应返回刷新令牌"
    assert body["user"]["username"] == "admin"


async def test_login_wrong_password(client: httpx.AsyncClient):
    """错误密码登录应 401"""
    resp = await client.post(
        f"{BASE}/login", data={"username": "admin", "password": "wrong-password"}
    )
    assert resp.status_code == 401, resp.text


async def test_login_oauth2_token(client: httpx.AsyncClient):
    """OAuth2 标准端点应返回 bearer 格式令牌(Swagger Authorize 用)"""
    resp = await client.post(
        f"{BASE}/token", data={"username": "admin", "password": "admin123"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"], "应返回 access_token"
    assert body["token_type"] == "bearer"


async def test_me(client: httpx.AsyncClient):
    """获取当前登录用户信息"""
    resp = await client.get(f"{BASE}/me")
    assert resp.status_code == 200, resp.text
    assert resp.json()["username"] == "admin"


async def test_me_id(client: httpx.AsyncClient):
    """获取当前登录用户ID(纯字符串)"""
    resp = await client.get(f"{BASE}/me-id")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    uid = body if isinstance(body, str) else body.get("user_id") or body.get("id")
    assert uid, "应返回非空用户ID"


async def test_me_permissions(client: httpx.AsyncClient):
    """获取当前用户角色与权限码"""
    resp = await client.get(f"{BASE}/me-permissions")
    assert resp.status_code == 200, resp.text


async def test_me_without_token(anon_client: httpx.AsyncClient):
    """无令牌访问受保护端点应 401"""
    resp = await anon_client.get(f"{BASE}/me")
    assert resp.status_code == 401, resp.text


async def test_register_and_cleanup(client: httpx.AsyncClient):
    """注册新用户成功,并清理测试用户"""
    username = f"test_reg_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    resp = await client.post(
        f"{BASE}/register",
        json={"username": username, "password": "Test@123456"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["username"] == username, "注册应返回新用户信息"
    assert body["tokens"]["access"]["token"], "注册应自动登录返回令牌"

    # 清理: 删除测试用户
    user_id = body["user"]["id"]
    resp_del = await client.delete(f"/authorization/users/{user_id}")
    assert resp_del.status_code in (200, 204), resp_del.text


async def test_refresh_token(client: httpx.AsyncClient):
    """用刷新令牌换取新的访问令牌"""
    login = (await client.post(
        f"{BASE}/login", data={"username": "admin", "password": "admin123"}
    )).json()
    refresh_token = login["tokens"]["refresh"]["token"]
    resp = await client.post(f"{BASE}/refresh", json={"token_refresh": refresh_token})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token"], "应返回新访问令牌"


async def test_logout_invalidates_token(client: httpx.AsyncClient):
    """登出后原访问令牌立即失效(独立登录的令牌,不影响其他用例)"""
    # 独立登录一份新令牌用于登出
    login = (await client.post(
        f"{BASE}/login", data={"username": "admin", "password": "admin123"}
    )).json()
    tokens = login["tokens"]
    headers = {"Authorization": f"Bearer {tokens['access']['token']}"}

    resp = await client.post(
        f"{BASE}/logout",
        headers=headers,
        json={
            "token_access": tokens["access"]["token"],
            "token_refresh": tokens["refresh"]["token"],
            "token_refresh_id": tokens["refresh"]["token_id"],
        },
    )
    assert resp.status_code == 200, resp.text

    # 原访问令牌应已被拉黑
    resp_me = await client.get(f"{BASE}/me", headers=headers)
    assert resp_me.status_code == 401, "登出后原令牌应失效"
