# -*- coding: utf-8 -*-
"""module_site 备忘业务线接口测试(/site/todolists)

覆盖: CRUD 全流程、分页过滤、日历 range 接口(年/月/周数据源)、
归属隔离、权限收紧(403/401)
"""

import time

import httpx

BASE = "/site/todolists"


def _suffix() -> str:
    """时间戳唯一后缀, 避免重复执行/并发时数据串扰"""
    return str(int(time.time() * 1000))


async def test_memo_crud_flow(client: httpx.AsyncClient):
    """备忘 创建→查询→更新→删除→重复删除404 全流程"""
    suffix = _suffix()
    name = f"测试备忘_{suffix}"
    created_id = None
    try:
        # 创建(指定日历时间)
        resp = await client.post(
            BASE,
            json={
                "name": name,
                "value": "备忘全文内容, 用于周视图前200字摘录",
                "start_at": "2026-03-10T09:00:00+08:00",
            },
        )
        assert resp.status_code == 201, resp.text
        created_id = resp.json()
        assert isinstance(created_id, str) and created_id

        # 查询单个
        resp = await client.get(f"{BASE}/{created_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["name"] == name
        assert body["status"] == "todo", "默认状态应为 todo"
        assert "前200字摘录" in body["value"]

        # 更新(改名/改状态/改时间)
        new_name = f"改名备忘_{suffix}"
        resp = await client.put(
            f"{BASE}/{created_id}",
            json={"name": new_name, "status": "done", "start_at": "2026-03-12T10:00:00+08:00"},
        )
        assert resp.status_code == 204, resp.text

        resp = await client.get(f"{BASE}/{created_id}")
        body = resp.json()
        assert body["name"] == new_name
        assert body["status"] == "done"

        # 删除
        resp = await client.delete(f"{BASE}/{created_id}")
        assert resp.status_code == 204, resp.text

        # 删除后查询 → 404; 重复删除 → 404
        resp = await client.get(f"{BASE}/{created_id}")
        assert resp.status_code == 404, resp.text
        resp = await client.delete(f"{BASE}/{created_id}")
        assert resp.status_code == 404, resp.text
        created_id = None
    finally:
        if created_id:
            await client.delete(f"{BASE}/{created_id}")


async def test_memo_list_filter(client: httpx.AsyncClient):
    """分页列表: 名称模糊 + 状态过滤"""
    suffix = _suffix()
    name = f"过滤备忘_{suffix}"
    created_id = None
    try:
        resp = await client.post(BASE, json={"name": name, "value": "过滤"})
        assert resp.status_code == 201, resp.text
        created_id = resp.json()

        # 名称模糊过滤
        resp = await client.get(
            f"{BASE}/list", params={"page": 1, "size": 50, "name": name}
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] >= 1
        assert any(item["id"] == created_id for item in data["items"])

        # 状态过滤: 未完成的备忘不出现在 done 过滤结果中
        resp = await client.get(
            f"{BASE}/list", params={"page": 1, "size": 50, "status": "done", "name": name}
        )
        assert all(item["status"] == "done" for item in resp.json()["items"])
    finally:
        if created_id:
            await client.delete(f"{BASE}/{created_id}")


async def test_memo_range_calendar(client: httpx.AsyncClient):
    """日历 range 接口: 月视图(1个月)与年视图(整年)时间范围查询"""
    suffix = _suffix()
    ids = []
    try:
        # 3条备忘: 3月两条 + 4月一条
        for start_at in (
            "2026-03-10T09:00:00+08:00",
            "2026-03-25T14:00:00+08:00",
            "2026-04-02T08:00:00+08:00",
        ):
            resp = await client.post(
                BASE, json={"name": f"日历备忘_{suffix}", "value": "内容", "start_at": start_at}
            )
            assert resp.status_code == 201, resp.text
            ids.append(resp.json())

        # 月视图范围: 2026-03 → 2条
        resp = await client.get(
            f"{BASE}/range",
            params={"start": "2026-03-01T00:00:00+08:00", "end": "2026-04-01T00:00:00+08:00"},
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()
        matched = [i for i in items if i["name"] == f"日历备忘_{suffix}"]
        assert len(matched) == 2, f"3月范围内应只有2条: {len(matched)}"

        # 年视图范围: 2026 整年 → 3条
        resp = await client.get(
            f"{BASE}/range",
            params={"start": "2026-01-01T00:00:00+08:00", "end": "2027-01-01T00:00:00+08:00"},
        )
        items = resp.json()
        matched = [i for i in items if i["name"] == f"日历备忘_{suffix}"]
        assert len(matched) == 3, f"整年范围应有3条: {len(matched)}"
    finally:
        for memo_id in ids:
            await client.delete(f"{BASE}/{memo_id}")


async def test_memo_ownership_isolation(
    client: httpx.AsyncClient, site_user: dict, site_grant
):
    """归属隔离: 普通用户(已授权)看不到也改不了管理员的备忘"""
    suffix = _suffix()
    name = f"管理员备忘_{suffix}"
    created_id = None
    user_id = site_user["user_id"]
    try:
        resp = await client.post(BASE, json={"name": name, "value": "管理员内容"})
        assert resp.status_code == 201, resp.text
        created_id = resp.json()

        # 授予普通用户 memo 读/改权限(fixture 结束自动回收)
        await site_grant(user_id, "memo", "read")
        await site_grant(user_id, "memo", "update")

        # 普通用户列表中不含管理员备忘
        resp = await client.get(
            f"{BASE}/list", params={"page": 1, "size": 50, "name": name},
            headers=site_user["headers"],
        )
        assert resp.status_code == 200, resp.text
        assert all(item["id"] != created_id for item in resp.json()["items"])

        # 普通用户直接查询管理员备忘 → 404
        resp = await client.get(f"{BASE}/{created_id}", headers=site_user["headers"])
        assert resp.status_code == 404, resp.text

        # 普通用户更新管理员备忘 → 404
        resp = await client.put(
            f"{BASE}/{created_id}", json={"name": "越权改名"}, headers=site_user["headers"]
        )
        assert resp.status_code == 404, resp.text
    finally:
        if created_id:
            await client.delete(f"{BASE}/{created_id}")


async def test_memo_permission_denied(
    client: httpx.AsyncClient, site_user: dict, anon_client: httpx.AsyncClient
):
    """权限收紧: default_policies=[] → 普通用户 403, 匿名 401"""
    resp = await client.post(BASE, json={"name": "无权限备忘"}, headers=site_user["headers"])
    assert resp.status_code == 403, resp.text

    resp = await client.get(f"{BASE}/list", headers=site_user["headers"])
    assert resp.status_code == 403, resp.text

    resp = await anon_client.get(f"{BASE}/list")
    assert resp.status_code == 401, resp.text
