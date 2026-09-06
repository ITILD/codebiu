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


async def test_update_my_profile(client: httpx.AsyncClient):
    """自助更新个人资料(昵称/邮箱),无需管理员权限"""
    resp = await client.put(
        f"{BASE}/me",
        json={"nickname": "自助昵称", "email": "self_profile@example.com"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["nickname"] == "自助昵称"
    assert body["email"] == "self_profile@example.com"


async def test_update_my_profile_without_token(anon_client: httpx.AsyncClient):
    """无令牌更新个人资料应 401"""
    resp = await anon_client.put(f"{BASE}/me", json={"nickname": "x"})
    assert resp.status_code == 401, resp.text


async def test_change_my_password_flow(client: httpx.AsyncClient):
    """自助修改密码全流程: 注册临时用户→改密→旧密码失效/新密码可登录→清理"""
    username = f"test_pwd_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    # 注册临时用户(注册响应携带该用户自己的令牌)
    reg = (await client.post(
        f"{BASE}/register", json={"username": username, "password": "Test@123456"}
    )).json()
    assert reg["user"]["username"] == username, resp_text_ok(reg)
    user_headers = {"Authorization": f"Bearer {reg['tokens']['access']['token']}"}

    try:
        # 旧密码错误应 400
        resp = await client.put(
            f"{BASE}/me/password",
            headers=user_headers,
            json={"old_password": "WrongOld@123", "new_password": "NewPass@456"},
        )
        assert resp.status_code == 400, resp.text

        # 正确修改密码(204)
        resp = await client.put(
            f"{BASE}/me/password",
            headers=user_headers,
            json={"old_password": "Test@123456", "new_password": "NewPass@456"},
        )
        assert resp.status_code == 204, resp.text

        # 旧密码登录失败
        resp = await client.post(
            f"{BASE}/login", data={"username": username, "password": "Test@123456"}
        )
        assert resp.status_code == 401, resp.text

        # 新密码登录成功
        resp = await client.post(
            f"{BASE}/login", data={"username": username, "password": "NewPass@456"}
        )
        assert resp.status_code == 200, resp.text
    finally:
        # 清理临时用户
        await client.delete(f"/authorization/users/{reg['user']['id']}")


def resp_text_ok(body: dict) -> str:
    """注册响应断言辅助(失败时输出响应体)"""
    return str(body)
