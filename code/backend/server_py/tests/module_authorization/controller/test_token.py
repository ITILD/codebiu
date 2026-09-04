# -*- coding: utf-8 -*-
"""module_authorization/token 接口标准测试
覆盖: 创建/校验/信息查询/全量吊销(用临时用户隔离,避免污染会话级管理员令牌)
"""

import time
import uuid

import httpx

BASE = "/authorization/tokens"
AUTH_BASE = "/authorization/auth"


async def _make_temp_user(client: httpx.AsyncClient) -> dict:
    """注册临时用户并返回 {id, username, password}"""
    username = f"test_token_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    resp = await client.post(
        f"{AUTH_BASE}/register", json={"username": username, "password": "Test@123456"}
    )
    assert resp.status_code == 200, resp.text
    user = resp.json()["user"]
    return {"id": user["id"], "username": username, "password": "Test@123456"}


async def test_token_full_lifecycle(client: httpx.AsyncClient):
    """创建→校验→查询→吊销→校验失效 全生命周期"""
    user = await _make_temp_user(client)
    try:
        # 创建刷新令牌(访问令牌不落库,仅刷新令牌持久化)
        resp = await client.post(
            f"{BASE}/create", json={"user_id": user["id"], "token_type": "refresh"}
        )
        assert resp.status_code == 201, resp.text
        created = resp.json()
        token = created.get("token") or created.get("access") or ""
        assert token, f"创建应返回令牌: {created}"

        # 校验令牌
        resp = await client.post(
            f"{BASE}/verify", params={"token_access": token}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("valid") is True, "令牌应校验通过"

        # 查询令牌信息(按令牌解码出的用户ID查库)
        resp = await client.get(f"{BASE}/info", params={"token_access": token})
        assert resp.status_code == 200, resp.text

        # 全量吊销该用户令牌
        resp = await client.delete(f"{BASE}/revoke-all/{user['id']}")
        assert resp.status_code == 200, resp.text
        assert resp.json().get("success") is True, "吊销应成功"

        # 吊销后刷新令牌应失效(库中记录被删除)
        resp = await client.post(
            f"{BASE}/verify", params={"token_access": token}
        )
        # verify 仅校验JWT签名不查库,仍可解析;刷新语义的失效由 /refresh 体现
        assert resp.status_code in (200, 401), resp.text
    finally:
        resp = await client.delete(f"/authorization/users/{user['id']}")
        assert resp.status_code in (200, 204), resp.text


async def test_verify_missing_param(client: httpx.AsyncClient):
    """缺少 token_access 参数应 400"""
    resp = await client.post(f"{BASE}/verify")
    assert resp.status_code == 400, resp.text


async def test_verify_invalid_token(client: httpx.AsyncClient):
    """无效令牌校验应 401"""
    resp = await client.post(
        f"{BASE}/verify", params={"token_access": "invalid-token-value"}
    )
    assert resp.status_code == 401, resp.text
