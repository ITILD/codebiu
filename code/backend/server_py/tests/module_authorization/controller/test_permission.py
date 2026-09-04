# -*- coding: utf-8 -*-
"""module_authorization/permission 接口标准测试
覆盖: 创建/树/分页列表/查询/按code/按parent/更新/删除
"""

import time
import uuid

import httpx

BASE = "/authorization/permissions"


def _make_perm() -> dict:
    """构造唯一测试权限节点数据"""
    return {
        "name": f"测试权限{int(time.time() * 1000)}",
        "code": f"test:perm:{uuid.uuid4().hex[:8]}",
        "menu_type": "C",
        "description": "接口测试自动创建",
    }


async def test_permission_crud_flow(client: httpx.AsyncClient):
    """创建→查询→按code查询→更新→删除 全流程"""
    data = _make_perm()
    resp = await client.post(BASE, json=data)
    assert resp.status_code in (200, 201), resp.text
    created = resp.json()
    # 创建接口直接返回权限ID字符串
    perm_id = created if isinstance(created, str) else (created.get("id") or created.get("permission_id"))
    assert perm_id, f"创建应返回权限ID: {created}"

    # 查询单个
    resp = await client.get(f"{BASE}/{perm_id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["code"] == data["code"]

    # 按 code 查询
    resp = await client.get(f"{BASE}/code/{data['code']}")
    assert resp.status_code == 200, resp.text

    # 更新名称
    resp = await client.put(f"{BASE}/{perm_id}", json={"name": "改名后的权限"})
    assert resp.status_code in (200, 204), resp.text
    resp = await client.get(f"{BASE}/{perm_id}")
    assert resp.json()["name"] == "改名后的权限"

    # 删除
    resp = await client.delete(f"{BASE}/{perm_id}")
    assert resp.status_code in (200, 204), resp.text


async def test_permission_tree(client: httpx.AsyncClient):
    """权限树应返回树形数组且非空(系统权限声明已注册)"""
    resp = await client.get(f"{BASE}/tree")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list), "树应返回数组"
    assert len(body) > 0, "系统权限树不应为空"


async def test_permission_list(client: httpx.AsyncClient):
    """分页列表应返回分页结构"""
    resp = await client.get(f"{BASE}/list", params={"page": 1, "size": 10})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("items") is not None or body.get("list") is not None


async def test_permission_parent_children(client: httpx.AsyncClient):
    """父子权限: 创建子节点后可按 parent 查询"""
    parent = _make_perm()
    parent["menu_type"] = "M"  # 目录
    resp = await client.post(BASE, json=parent)
    assert resp.status_code in (200, 201), resp.text
    # 创建接口直接返回权限ID字符串
    created = resp.json()
    parent_id = created if isinstance(created, str) else created.get("id")
    assert parent_id, resp.text

    child = _make_perm()
    child["parent_id"] = parent_id
    child["menu_type"] = "F"  # 按钮
    resp = await client.post(BASE, json=child)
    assert resp.status_code in (200, 201), resp.text
    created = resp.json()
    child_id = created if isinstance(created, str) else created.get("id")
    assert child_id, resp.text

    # 按父ID查询子节点
    resp = await client.get(f"{BASE}/parent/{parent_id}")
    assert resp.status_code == 200, resp.text

    await client.delete(f"{BASE}/{child_id}")
    await client.delete(f"{BASE}/{parent_id}")
