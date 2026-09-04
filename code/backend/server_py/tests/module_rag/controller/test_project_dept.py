# -*- coding: utf-8 -*-
"""module_rag/project_dept 接口标准测试
覆盖: 添加部门授权/授权列表(档位过滤)/更新档位/移除/重复授权/非法角色/部门树
注意: 授权前会校验项目与部门存在性;部门通过 /authorization/depts 创建(管理员有 sys:dept:create 权限)
"""

import time
import uuid

import httpx

PROJECT_BASE = "/rag/projects"
DEPT_BASE = "/authorization/depts"
BASE = "/rag/project-depts"


def _make_project() -> dict:
    """构造唯一测试项目数据"""
    return {
        "name": f"部门授权测试项目_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
        "description": "项目部门授权接口测试",
        "is_private": True,
        "kb_category": "project",
    }


async def _create_project(client: httpx.AsyncClient) -> str:
    """创建测试项目并返回项目ID"""
    resp = await client.post(PROJECT_BASE, json=_make_project())
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_dept(client: httpx.AsyncClient) -> str:
    """创建测试部门并返回部门ID"""
    resp = await client.post(
        DEPT_BASE,
        json={"name": f"授权测试部门{int(time.time() * 1000)}_{uuid.uuid4().hex[:4]}", "order_num": 99},
    )
    assert resp.status_code in (200, 201), resp.text
    dept_id = resp.json().get("id")
    assert dept_id, f"创建应返回部门ID: {resp.text}"
    return dept_id


async def test_dept_auth_crud_flow(client: httpx.AsyncClient):
    """添加部门授权→列表→更新档位→移除 全流程"""
    project_id = await _create_project(client)
    dept_id = await _create_dept(client)
    auth_id = None
    try:
        # 添加部门授权(project_reader)
        resp = await client.post(
            BASE,
            json={"project_id": project_id, "dept_id": dept_id, "role": "project_reader"},
        )
        assert resp.status_code == 201, resp.text
        auth_id = resp.json()
        assert isinstance(auth_id, str) and auth_id, f"应返回授权记录ID: {resp.text}"

        # 授权列表应包含该记录
        resp = await client.get(
            f"{BASE}/project/{project_id}", params={"page": 1, "size": 50}
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        matched = [a for a in items if a["id"] == auth_id]
        assert matched, "授权列表应包含新授权记录"
        assert matched[0]["dept_id"] == dept_id
        assert matched[0]["role"] == "project_reader"

        # 更新档位(200 返回更新后的记录)
        resp = await client.put(f"{BASE}/{auth_id}", json={"role": "project_editor"})
        assert resp.status_code in (200, 204), resp.text
        if resp.status_code == 200:
            assert resp.json()["role"] == "project_editor", "更新响应应携带新档位"

        # 档位过滤验证更新生效
        resp = await client.get(
            f"{BASE}/project/{project_id}",
            params={"page": 1, "size": 50, "role": "project_editor"},
        )
        assert resp.status_code == 200, resp.text
        assert any(a["id"] == auth_id for a in resp.json()["items"]), "档位过滤应命中更新后的记录"

        # 移除授权(204)
        resp = await client.delete(f"{BASE}/{auth_id}")
        assert resp.status_code in (200, 204), resp.text
        removed_auth_id = auth_id
        auth_id = None  # 已删除,finally 无需重复清理

        # 移除后列表不应再包含
        resp = await client.get(
            f"{BASE}/project/{project_id}", params={"page": 1, "size": 50}
        )
        assert resp.status_code == 200, resp.text
        assert not any(
            a["id"] == removed_auth_id for a in resp.json()["items"]
        ), "移除后列表不应再包含该授权"
    finally:
        if auth_id:
            # 尽力清理授权记录(避免阻碍部门删除)
            await client.delete(f"{BASE}/{auth_id}")
        # 清理部门与项目(项目删除级联清理授权记录)
        await client.delete(f"{DEPT_BASE}/{dept_id}")
        await client.delete(f"{PROJECT_BASE}/{project_id}")


async def test_add_dept_auth_invalid_role(client: httpx.AsyncClient):
    """添加授权使用非法档位应 400"""
    project_id = await _create_project(client)
    dept_id = await _create_dept(client)
    try:
        resp = await client.post(
            BASE,
            json={"project_id": project_id, "dept_id": dept_id, "role": "super_god"},
        )
        assert resp.status_code == 400, f"非法档位应 400: {resp.text}"
    finally:
        await client.delete(f"{DEPT_BASE}/{dept_id}")
        await client.delete(f"{PROJECT_BASE}/{project_id}")


async def test_add_dept_auth_duplicate_rejected(client: httpx.AsyncClient):
    """同一项目同一部门重复授权应 400"""
    project_id = await _create_project(client)
    dept_id = await _create_dept(client)
    auth_id = None
    try:
        resp = await client.post(
            BASE,
            json={"project_id": project_id, "dept_id": dept_id, "role": "project_reader"},
        )
        assert resp.status_code == 201, resp.text
        auth_id = resp.json()

        # 重复授权应被拒绝
        resp = await client.post(
            BASE,
            json={"project_id": project_id, "dept_id": dept_id, "role": "project_editor"},
        )
        assert resp.status_code == 400, f"重复授权应 400: {resp.text}"
    finally:
        if auth_id:
            await client.delete(f"{BASE}/{auth_id}")
        await client.delete(f"{DEPT_BASE}/{dept_id}")
        await client.delete(f"{PROJECT_BASE}/{project_id}")


async def test_add_dept_auth_nonexistent_dept(client: httpx.AsyncClient):
    """对不存在的部门授权应 400(存在性校验)"""
    project_id = await _create_project(client)
    try:
        resp = await client.post(
            BASE,
            json={
                "project_id": project_id,
                "dept_id": f"no-such-dept-{uuid.uuid4().hex[:8]}",
                "role": "project_reader",
            },
        )
        assert resp.status_code == 400, f"部门不存在应 400: {resp.text}"
    finally:
        await client.delete(f"{PROJECT_BASE}/{project_id}")


async def test_nonexistent_auth_update_remove(client: httpx.AsyncClient):
    """更新/移除不存在的授权记录应 404(该分支在 try 外抛出,透传正确)"""
    fake_id = f"no-such-auth-{uuid.uuid4().hex[:8]}"
    resp = await client.put(f"{BASE}/{fake_id}", json={"role": "project_editor"})
    assert resp.status_code == 404, resp.text
    resp = await client.delete(f"{BASE}/{fake_id}")
    assert resp.status_code == 404, resp.text


async def test_dept_tree_only_login_required(client: httpx.AsyncClient):
    """/rag/project-depts/dept-tree 仅需登录即可获取部门树(区别于 sys:dept:read 档位)"""
    resp = await client.get(f"{BASE}/dept-tree")
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list), "部门树应返回数组"
