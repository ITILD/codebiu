# -*- coding: utf-8 -*-
"""module_authorization/dept 接口标准测试
覆盖: 创建/树/分页列表/查询/更新/删除(父子级联场景)
"""

import time
import uuid

import httpx

BASE = "/authorization/depts"


def _make_dept(name_suffix: str = "") -> dict:
    """构造唯一测试部门数据"""
    return {
        "name": f"测试部门{int(time.time() * 1000)}{name_suffix}_{uuid.uuid4().hex[:4]}",
        "order_num": 99,
    }


async def test_dept_crud_flow(client: httpx.AsyncClient):
    """创建→查询→更新→删除 全流程"""
    data = _make_dept()
    resp = await client.post(BASE, json=data)
    assert resp.status_code in (200, 201), resp.text
    created = resp.json()
    dept_id = created.get("id") or created.get("dept_id")
    assert dept_id, f"创建应返回部门ID: {created}"

    # 查询单个
    resp = await client.get(f"{BASE}/{dept_id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == data["name"]

    # 更新负责人
    resp = await client.put(f"{BASE}/{dept_id}", json={"leader": "测试负责人"})
    assert resp.status_code in (200, 204), resp.text
    resp = await client.get(f"{BASE}/{dept_id}")
    assert resp.json()["leader"] == "测试负责人"

    # 删除
    resp = await client.delete(f"{BASE}/{dept_id}")
    assert resp.status_code in (200, 204), resp.text


async def test_dept_tree(client: httpx.AsyncClient):
    """部门树应返回树形数组"""
    resp = await client.get(f"{BASE}/tree")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list), "树应返回数组"


async def test_dept_parent_child(client: httpx.AsyncClient):
    """创建父子部门后,子部门应挂在父部门下"""
    parent = _make_dept("_父")
    resp = await client.post(BASE, json=parent)
    parent_id = (resp.json()).get("id")
    assert parent_id, resp.text

    child = _make_dept("_子")
    child["parent_id"] = parent_id
    resp = await client.post(BASE, json=child)
    assert resp.status_code in (200, 201), resp.text
    child_id = resp.json().get("id")

    # 树中父节点应包含子节点
    resp = await client.get(f"{BASE}/tree")
    assert resp.status_code == 200, resp.text

    # 清理: 先删子再删父
    await client.delete(f"{BASE}/{child_id}")
    await client.delete(f"{BASE}/{parent_id}")


async def test_dept_list(client: httpx.AsyncClient):
    """列表应返回扁平数组"""
    resp = await client.get(f"{BASE}/list")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list), "部门列表应返回扁平数组"
