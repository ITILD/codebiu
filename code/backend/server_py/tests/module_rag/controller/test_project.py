# -*- coding: utf-8 -*-
"""module_rag/project 接口标准测试
覆盖: 创建/查询/分页列表(名称/分类/私有过滤)/更新/删除 全流程
注意: 项目创建后创建者自动成为项目管理员(project_admin),项目删除会级联清理成员/文档/部门授权
"""

import time
import uuid

import httpx

BASE = "/rag/projects"
MEMBER_BASE = "/rag/project-members"


def _make_project() -> dict:
    """构造唯一测试项目数据(名称带时间戳+随机后缀)"""
    return {
        "name": f"测试项目_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
        "description": "接口测试项目描述",
        "is_private": True,
        "kb_category": "project",
    }


async def _create_project(client: httpx.AsyncClient, data: dict) -> str:
    """创建测试项目并返回项目ID"""
    resp = await client.post(BASE, json=data)
    assert resp.status_code == 201, resp.text
    project_id = resp.json()
    assert isinstance(project_id, str) and project_id, f"创建应返回项目ID字符串: {resp.text}"
    return project_id


async def test_project_crud_flow(client: httpx.AsyncClient):
    """创建→查询→更新→删除 全流程"""
    data = _make_project()
    project_id = await _create_project(client, data)
    try:
        # 查询单个: 字段应由系统填充 created_by
        resp = await client.get(f"{BASE}/{project_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["name"] == data["name"], "项目名应一致"
        assert body["kb_category"] == "project"
        assert body["is_private"] is True
        assert body["created_by"], "created_by 应由系统从 token 自动填充"

        # 更新(204)
        resp = await client.put(
            f"{BASE}/{project_id}",
            json={"description": "更新后的描述", "is_private": False},
        )
        assert resp.status_code in (200, 204), resp.text

        # 验证更新生效
        resp = await client.get(f"{BASE}/{project_id}")
        body = resp.json()
        assert body["description"] == "更新后的描述", "描述应已更新"
        assert body["is_private"] is False, "私有状态应已更新"
    finally:
        # 删除项目(级联清理)
        resp = await client.delete(f"{BASE}/{project_id}")
        assert resp.status_code in (200, 204), resp.text

    # 删除后查询: 应返回 404(404 被包装成 500 的缺陷已修复)
    resp = await client.get(f"{BASE}/{project_id}")
    assert resp.status_code == 404, resp.text


async def test_project_creator_becomes_admin(client: httpx.AsyncClient):
    """创建者应自动成为项目管理员(project_admin)"""
    data = _make_project()
    project_id = await _create_project(client, data)
    try:
        resp = await client.get(
            f"{MEMBER_BASE}/project/{project_id}", params={"page": 1, "size": 50}
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert items, "创建项目后成员列表不应为空(创建者自动加入)"
        roles = [m["role"] for m in items]
        assert "project_admin" in roles, f"创建者应为项目管理员: {roles}"
    finally:
        await client.delete(f"{BASE}/{project_id}")


async def test_project_list_and_filters(client: httpx.AsyncClient):
    """分页列表 + 名称/分类过滤 + 无效分类 400"""
    data = _make_project()
    project_id = await _create_project(client, data)
    try:
        # 名称模糊过滤应命中刚创建的项目
        resp = await client.get(
            f"{BASE}/list", params={"page": 1, "size": 10, "name": data["name"]}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 1, "名称过滤应至少命中 1 条"
        assert any(item["id"] == project_id for item in body["items"]), "结果应包含新项目"

        # 分类过滤(personal 与创建时的 project 不同,正常返回即可)
        resp = await client.get(
            f"{BASE}/list", params={"page": 1, "size": 10, "kb_category": "personal"}
        )
        assert resp.status_code == 200, resp.text

        # 无效 kb_category 应 400
        resp = await client.get(
            f"{BASE}/list", params={"page": 1, "size": 10, "kb_category": "invalid_category"}
        )
        assert resp.status_code == 400, f"无效分类应 400: {resp.text}"
    finally:
        await client.delete(f"{BASE}/{project_id}")


async def test_project_get_not_found(client: httpx.AsyncClient):
    """查询不存在的项目 → 404(404 被包装为 500 的缺陷已修复)"""
    resp = await client.get(f"{BASE}/no-such-project-{uuid.uuid4().hex[:8]}")
    assert resp.status_code == 404, resp.text


async def test_project_update_invalid_category(client: httpx.AsyncClient):
    """更新为无效知识库分类应 400"""
    data = _make_project()
    project_id = await _create_project(client, data)
    try:
        resp = await client.put(
            f"{BASE}/{project_id}", json={"kb_category": "invalid_category"}
        )
        assert resp.status_code == 400, f"无效分类更新应 400: {resp.text}"
    finally:
        await client.delete(f"{BASE}/{project_id}")
