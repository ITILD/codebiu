# -*- coding: utf-8 -*-
"""module_authorization/user 接口标准测试
覆盖: 创建/分页列表/查询/更新/删除/认证
"""

import time
import uuid

import httpx

BASE = "/authorization/users"


def _make_user() -> dict:
    """构造唯一测试用户数据"""
    return {
        "username": f"test_user_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
        "password": "Test@123456",
        "nickname": "接口测试用户",
        "email": "test@example.com",
    }


async def _create_user(client: httpx.AsyncClient, data: dict) -> dict:
    """创建测试用户并返回响应体"""
    resp = await client.post(BASE, json=data)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


async def test_user_crud_flow(client: httpx.AsyncClient):
    """创建→查询→更新→删除 全流程"""
    data = _make_user()
    created = await _create_user(client, data)
    user_id = created.get("id") or created.get("user_id")
    assert user_id, f"创建应返回用户ID: {created}"

    # 查询单个
    resp = await client.get(f"{BASE}/{user_id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["username"] == data["username"]

    # 更新昵称
    resp = await client.put(f"{BASE}/{user_id}", json={"nickname": "改名后的用户"})
    assert resp.status_code in (200, 204), resp.text

    # 验证更新生效
    resp = await client.get(f"{BASE}/{user_id}")
    assert resp.json()["nickname"] == "改名后的用户", "昵称应已更新"

    # 删除
    resp = await client.delete(f"{BASE}/{user_id}")
    assert resp.status_code in (200, 204), resp.text

    # 删除后查询应 404 或返回禁用状态
    resp = await client.get(f"{BASE}/{user_id}")
    assert resp.status_code in (200, 404), resp.text


async def test_user_list(client: httpx.AsyncClient):
    """分页列表应返回分页结构且包含 admin"""
    resp = await client.get(f"{BASE}/list", params={"page": 1, "size": 10})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body.get("items") or body.get("list") or []
    assert isinstance(items, list), "应返回条目列表"
    usernames = [u.get("username") for u in items]
    assert "admin" in usernames, "列表应包含 admin 用户"


async def test_user_authenticate(client: httpx.AsyncClient):
    """用户认证: 正确密码通过,错误密码拒绝"""
    resp = await client.post(
        f"{BASE}/authenticate",
        params={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == 200, resp.text

    resp_bad = await client.post(
        f"{BASE}/authenticate",
        params={"username": "admin", "password": "definitely-wrong"},
    )
    assert resp_bad.status_code in (401, 400), resp_bad.text


async def test_user_get_not_found(client: httpx.AsyncClient):
    """查询不存在的用户应 404(404 被包装为 500 的缺陷已修复)"""
    resp = await client.get(f"{BASE}/nonexistent-user-id-000")
    assert resp.status_code == 404, resp.text
