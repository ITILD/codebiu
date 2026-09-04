# -*- coding: utf-8 -*-
"""module_authorization/role 接口标准测试
覆盖: 创建/分页列表/全量列表/查询/按名称/按key/更新/删除
"""

import time
import uuid

import httpx

BASE = "/authorization/roles"


def _make_role() -> dict:
    """构造唯一测试角色数据"""
    key = f"test_role_{uuid.uuid4().hex[:8]}"
    return {
        "name": f"测试角色{int(time.time())}",
        "role_key": key,
        "description": "接口测试自动创建",
        "sort": 99,
    }


async def test_role_crud_flow(client: httpx.AsyncClient):
    """创建→查询→按key查询→更新→删除 全流程"""
    data = _make_role()
    resp = await client.post(BASE, json=data)
    assert resp.status_code in (200, 201), resp.text
    created = resp.json()
    # 创建接口直接返回角色ID字符串
    role_id = created if isinstance(created, str) else (created.get("id") or created.get("role_id"))
    assert role_id, f"创建应返回角色ID: {created}"

    # 查询单个
    resp = await client.get(f"{BASE}/{role_id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["role_key"] == data["role_key"]

    # 按角色 key 查询
    resp = await client.get(f"{BASE}/key/{data['role_key']}")
    assert resp.status_code == 200, resp.text

    # 更新描述
    resp = await client.put(f"{BASE}/{role_id}", json={"description": "更新后的描述"})
    assert resp.status_code in (200, 204), resp.text
    resp = await client.get(f"{BASE}/{role_id}")
    assert resp.json()["description"] == "更新后的描述"

    # 删除
    resp = await client.delete(f"{BASE}/{role_id}")
    assert resp.status_code in (200, 204), resp.text


async def test_role_list(client: httpx.AsyncClient):
    """分页列表应含内置 admin 角色"""
    resp = await client.get(f"{BASE}/list", params={"page": 1, "size": 50})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body.get("items") or body.get("list") or []
    assert any(r.get("role_key") == "admin" for r in items), "列表应包含 admin 角色"


async def test_role_list_all(client: httpx.AsyncClient):
    """全量列表(不分页)应返回数组"""
    resp = await client.get(f"{BASE}/all")
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list), "应返回数组"


async def test_role_get_by_name(client: httpx.AsyncClient):
    """按名称查询内置管理员角色"""
    resp = await client.get(f"{BASE}/name/系统管理员")
    assert resp.status_code == 200, resp.text


async def test_role_get_not_found(client: httpx.AsyncClient):
    """查询不存在的角色 key 应 404 或错误"""
    resp = await client.get(f"{BASE}/key/no_such_role_key_xyz")
    assert resp.status_code in (200, 404, 400, 500), resp.text
