# -*- coding: utf-8 -*-
"""module_little_utils/todolist 接口标准测试
覆盖: 创建/查询单个/更新/删除 全流程、分页过滤、滚动加载、参数校验、404分支

注: src/app.py 中 module_little_utils 控制器导入当前被注释,
路由 /little-utils 不会随主应用挂载, 此处显式导入控制器模块触发挂载。

已知缺陷(以实际接口行为为准做兼容断言):
- GET /{id} 不存在时: 控制器 except Exception 会将内部 404 HTTPException
  重新包装为 500(未像其它模块那样先 except HTTPException: raise)。
"""

import time

import httpx

# 触发 /little-utils 子应用挂载(否则主应用无该路由)
import module_little_utils.controller.todolist  # noqa: F401

BASE = "/little-utils/todolists"


def _suffix() -> str:
    """时间戳唯一后缀, 避免重复执行/并发时数据串扰"""
    return str(int(time.time() * 1000))


async def test_todolist_crud_flow(client: httpx.AsyncClient):
    """创建→查询→更新→删除 全流程"""
    suffix = _suffix()
    name = f"测试计划_{suffix}"
    created_id = None
    try:
        # 创建(默认状态 todo)
        resp = await client.post(
            BASE,
            json={
                "name": name,
                "value": "接口测试内容",
                "description": "自动化测试数据",
            },
        )
        assert resp.status_code == 201, resp.text
        created_id = resp.json()
        assert isinstance(created_id, str) and created_id, f"创建应返回ID字符串: {created_id}"

        # 查询单个
        resp = await client.get(f"{BASE}/{created_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["name"] == name
        assert body["status"] == "todo", "默认状态应为 todo"
        assert body["value"] == "接口测试内容"

        # 更新(改名称与状态)
        new_name = f"改名计划_{suffix}"
        resp = await client.put(
            f"{BASE}/{created_id}", json={"name": new_name, "status": "done"}
        )
        assert resp.status_code in (200, 204), resp.text

        # 验证更新生效
        resp = await client.get(f"{BASE}/{created_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["name"] == new_name, "名称应已更新"
        assert body["status"] == "done", "状态应已更新"

        # 删除
        deleted_id = created_id
        created_id = None
        resp = await client.delete(f"{BASE}/{deleted_id}")
        assert resp.status_code in (200, 204), resp.text

        # 删除后查询: 应返回 404(404 包装为 500 的缺陷已修复)
        resp = await client.get(f"{BASE}/{deleted_id}")
        assert resp.status_code == 404, resp.text
    finally:
        # 兜底清理, 保证不依赖执行顺序
        if created_id:
            await client.delete(f"{BASE}/{created_id}")


async def test_todolist_list_filter(client: httpx.AsyncClient):
    """分页列表: 按 name 模糊 + status 过滤, 结果应包含刚创建的记录"""
    suffix = _suffix()
    name = f"列表过滤_{suffix}"
    created_id = None
    try:
        resp = await client.post(BASE, json={"name": name})
        assert resp.status_code == 201, resp.text
        created_id = resp.json()

        resp = await client.get(
            f"{BASE}/list",
            params={"page": 1, "size": 10, "name": name, "status": "todo"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        for key in ("items", "total", "page", "size", "pages"):
            assert key in body, f"分页响应缺少字段 {key}: {body}"
        assert body["total"] >= 1, "过滤结果总数应至少为 1"
        names = [item.get("name") for item in body["items"]]
        assert name in names, "过滤结果应包含刚创建的记录"
    finally:
        if created_id:
            await client.delete(f"{BASE}/{created_id}")


async def test_todolist_scroll(client: httpx.AsyncClient):
    """无限滚动: /scroll 路由注册在 /{id} 之前, 应正常返回滚动结构"""
    resp = await client.get(f"{BASE}/scroll", params={"limit": 5})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body["items"], list), "items 应为列表"
    assert isinstance(body["has_more"], bool), "has_more 应为布尔"
    assert len(body["items"]) <= 5, "返回条数不应超过 limit"


async def test_todolist_get_not_found(client: httpx.AsyncClient):
    """查询不存在的ID → 404(404 包装为 500 的缺陷已修复)"""
    resp = await client.get(f"{BASE}/not-exist-{_suffix()}")
    assert resp.status_code == 404, resp.text


async def test_todolist_create_validation(client: httpx.AsyncClient):
    """创建参数校验: 缺少必填 name / name 超长(max_length=100) → 422"""
    # 缺少 name 字段
    resp = await client.post(BASE, json={})
    assert resp.status_code == 422, resp.text

    # name 超过 100 字符
    resp = await client.post(BASE, json={"name": "x" * 101})
    assert resp.status_code == 422, resp.text
