# -*- coding: utf-8 -*-
"""module_rag/project_member 接口标准测试
覆盖: 添加成员/成员列表(角色过滤)/修改角色/移除/重复添加/非法角色/我参与的项目
注意: 成员列表联表用户表(user join),因此必须使用真实存在的用户ID;
      项目创建后创建者自动成为 project_admin,管理员拥有成员管理权限
"""

import time
import uuid

import httpx

PROJECT_BASE = "/rag/projects"
USER_BASE = "/authorization/users"
BASE = "/rag/project-members"


def _make_project() -> dict:
    """构造唯一测试项目数据"""
    return {
        "name": f"成员测试项目_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
        "description": "项目成员接口测试",
        "is_private": True,
        "kb_category": "project",
    }


def _make_user() -> dict:
    """构造唯一测试用户数据(作为被添加的成员)"""
    return {
        "username": f"rag_member_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
        "password": "Test@123456",
        "nickname": "RAG成员测试用户",
        "email": "rag-member-test@example.com",
    }


async def _create_project(client: httpx.AsyncClient) -> str:
    """创建测试项目并返回项目ID"""
    resp = await client.post(PROJECT_BASE, json=_make_project())
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_user(client: httpx.AsyncClient) -> str:
    """创建真实用户并返回用户ID(成员列表联表用户表,必须真实存在)"""
    resp = await client.post(USER_BASE, json=_make_user())
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    user_id = body.get("id") or body.get("user_id")
    assert user_id, f"创建应返回用户ID: {body}"
    return user_id


async def test_member_crud_flow(client: httpx.AsyncClient):
    """添加成员→查询→成员列表→修改角色→移除 全流程"""
    project_id = await _create_project(client)
    user_id = await _create_user(client)
    member_id = None
    try:
        # 添加成员(project_reader)
        resp = await client.post(
            BASE,
            json={"user_id": user_id, "project_id": project_id, "role": "project_reader"},
        )
        assert resp.status_code == 201, resp.text
        member_id = resp.json()
        assert isinstance(member_id, str) and member_id, f"应返回成员ID: {resp.text}"

        # 查询单个成员
        resp = await client.get(f"{BASE}/{member_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["user_id"] == user_id
        assert body["project_id"] == project_id
        assert body["role"] == "project_reader"

        # 成员列表应包含新成员
        resp = await client.get(
            f"{BASE}/project/{project_id}", params={"page": 1, "size": 50}
        )
        assert resp.status_code == 200, resp.text
        assert any(m["id"] == member_id for m in resp.json()["items"]), "列表应包含新成员"

        # 角色过滤: project_admin 应命中创建者(自动成为管理员)
        resp = await client.get(
            f"{BASE}/project/{project_id}",
            params={"page": 1, "size": 50, "role": "project_admin"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 1, "创建者(project_admin)应被过滤命中"
        assert all(m["role"] == "project_admin" for m in body["items"])

        # 修改角色(204)
        resp = await client.put(f"{BASE}/{member_id}", json={"role": "project_editor"})
        assert resp.status_code in (200, 204), resp.text
        resp = await client.get(f"{BASE}/{member_id}")
        assert resp.json()["role"] == "project_editor", "角色应已更新"

        # 移除成员(204)
        resp = await client.delete(f"{BASE}/{member_id}")
        assert resp.status_code in (200, 204), resp.text
        removed_member_id = member_id
        member_id = None  # 已删除,finally 无需重复清理

        # 移除后成员列表不应再包含该成员
        resp = await client.get(
            f"{BASE}/project/{project_id}", params={"page": 1, "size": 50}
        )
        assert resp.status_code == 200, resp.text
        assert not any(
            m["id"] == removed_member_id for m in resp.json()["items"]
        ), "移除后列表不应再包含该成员"
    finally:
        if member_id:
            # 尽力清理成员(失败不影响结果,项目删除会级联清理)
            await client.delete(f"{BASE}/{member_id}")
        # 清理用户与项目(项目删除级联清理成员/文档/部门授权)
        await client.delete(f"{USER_BASE}/{user_id}")
        await client.delete(f"{PROJECT_BASE}/{project_id}")


async def test_add_member_invalid_role(client: httpx.AsyncClient):
    """添加成员使用非法角色应 400"""
    project_id = await _create_project(client)
    try:
        resp = await client.post(
            BASE,
            json={
                "user_id": f"fake-user-{uuid.uuid4().hex[:8]}",
                "project_id": project_id,
                "role": "super_god",  # 非项目级三档角色
            },
        )
        assert resp.status_code == 400, f"非法角色应 400: {resp.text}"
    finally:
        await client.delete(f"{PROJECT_BASE}/{project_id}")


async def test_add_duplicate_member_rejected(client: httpx.AsyncClient):
    """重复添加同一成员应 400"""
    project_id = await _create_project(client)
    user_id = await _create_user(client)
    try:
        resp = await client.post(
            BASE,
            json={"user_id": user_id, "project_id": project_id, "role": "project_reader"},
        )
        assert resp.status_code == 201, resp.text

        # 重复添加应被拒绝
        resp = await client.post(
            BASE,
            json={"user_id": user_id, "project_id": project_id, "role": "project_editor"},
        )
        assert resp.status_code == 400, f"重复添加应 400: {resp.text}"
    finally:
        await client.delete(f"{USER_BASE}/{user_id}")
        await client.delete(f"{PROJECT_BASE}/{project_id}")


async def test_nonexistent_member(client: httpx.AsyncClient):
    """查询/更新/移除不存在的成员 → 均 404(查询 500 包装缺陷已修复)"""
    fake_id = f"no-such-member-{uuid.uuid4().hex[:8]}"
    resp = await client.get(f"{BASE}/{fake_id}")
    assert resp.status_code == 404, resp.text
    resp = await client.put(f"{BASE}/{fake_id}", json={"role": "project_editor"})
    assert resp.status_code == 404, resp.text
    resp = await client.delete(f"{BASE}/{fake_id}")
    assert resp.status_code == 404, resp.text


async def test_my_projects(client: httpx.AsyncClient):
    """我参与的项目列表应包含刚创建的项目(创建者自动加入)"""
    project = _make_project()
    resp = await client.post(PROJECT_BASE, json=project)
    assert resp.status_code == 201, resp.text
    project_id = resp.json()
    try:
        resp = await client.get(f"{BASE}/my", params={"page": 1, "size": 50})
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        mine = [item for item in items if item.get("project_id") == project_id]
        assert mine, "我参与的项目应包含新建项目"
        assert mine[0]["role"] == "project_admin", "我的角色应为项目管理员"
        assert mine[0]["project_name"] == project["name"]
    finally:
        await client.delete(f"{PROJECT_BASE}/{project_id}")
