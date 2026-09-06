# -*- coding: utf-8 -*-
"""module_site 记账业务线接口测试(/site/ledger/records)

覆盖: CRUD 全流程、月份/方向过滤、月度统计(概览/饼图/趋势)、
归属隔离、权限收紧(403/401)
"""

import time

import httpx

BASE = "/site/ledger/records"


def _suffix() -> str:
    """时间戳唯一后缀, 避免重复执行/并发时数据串扰"""
    return str(int(time.time() * 1000))


async def test_ledger_record_crud_flow(client: httpx.AsyncClient):
    """记账 创建→查询→更新→删除→重复删除404 全流程"""
    created_id = None
    try:
        # 创建(支出)
        resp = await client.post(
            BASE,
            json={
                "amount": 120.5,
                "flow_type": "expense",
                "category": "餐饮",
                "note": "午餐",
                "occurred_at": "2026-05-10",
            },
        )
        assert resp.status_code == 201, resp.text
        created_id = resp.json()
        assert isinstance(created_id, str) and created_id

        # 查询单个
        resp = await client.get(f"{BASE}/{created_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["amount"] == 120.5
        assert body["flow_type"] == "expense"
        assert body["category"] == "餐饮"
        assert body["occurred_at"].startswith("2026-05-10")

        # 更新(改金额/分类)
        resp = await client.put(
            f"{BASE}/{created_id}", json={"amount": 130, "category": "聚餐"}
        )
        assert resp.status_code == 204, resp.text

        resp = await client.get(f"{BASE}/{created_id}")
        body = resp.json()
        assert body["amount"] == 130
        assert body["category"] == "聚餐"

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


async def test_ledger_record_list_filter(client: httpx.AsyncClient):
    """分页列表: 月份 + 收支方向过滤"""
    ids = []
    try:
        for payload in (
            {"amount": 20, "flow_type": "expense", "category": "交通", "occurred_at": "2026-05-01"},
            {"amount": 30, "flow_type": "expense", "category": "交通", "occurred_at": "2026-05-02"},
            {"amount": 100, "flow_type": "income", "category": "红包", "occurred_at": "2026-06-01"},
        ):
            resp = await client.post(BASE, json=payload)
            assert resp.status_code == 201, resp.text
            ids.append(resp.json())

        # 月份过滤 2026-05 → 2条(且方向过滤 expense)
        resp = await client.get(
            f"{BASE}/list",
            params={"page": 1, "size": 50, "month": "2026-05", "flow_type": "expense"},
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert len(items) >= 2, "5月支出应有2条"
        assert all(item["flow_type"] == "expense" for item in items)
    finally:
        for record_id in ids:
            await client.delete(f"{BASE}/{record_id}")


async def test_ledger_stats(client: httpx.AsyncClient):
    """月度统计: 概览合计 + 支出分类饼图 + 近6月趋势"""
    ids = []
    try:
        for payload in (
            {"amount": 5000, "flow_type": "income", "category": "工资", "occurred_at": "2026-05-05"},
            {"amount": 120.5, "flow_type": "expense", "category": "餐饮", "occurred_at": "2026-05-10"},
            {"amount": 79.5, "flow_type": "expense", "category": "餐饮", "occurred_at": "2026-05-11"},
            {"amount": 50, "flow_type": "expense", "category": "交通", "occurred_at": "2026-05-12"},
        ):
            resp = await client.post(BASE, json=payload)
            assert resp.status_code == 201, resp.text
            ids.append(resp.json())

        resp = await client.get(f"{BASE}/stats", params={"month": "2026-05"})
        assert resp.status_code == 200, resp.text
        stats = resp.json()

        # 概览: 收入5000 支出250 结余4750
        assert stats["income_total"] == 5000
        assert stats["expense_total"] == 250
        assert stats["balance"] == 4750
        assert stats["month"] == "2026-05"

        # 饼图: 餐饮合计200(2笔)应排第一
        pie = stats["category_pie"]
        assert pie[0]["category"] == "餐饮"
        assert pie[0]["total"] == 200
        assert pie[0]["count"] == 2
        assert any(item["category"] == "交通" and item["total"] == 50 for item in pie)

        # 趋势: 近6个月(2025-12 ~ 2026-05), 最后一个月为当月
        trend = stats["trend"]
        assert len(trend) == 6
        assert trend[-1]["month"] == "2026-05"
        assert trend[-1]["income"] == 5000
        assert trend[-1]["expense"] == 250
        assert trend[0]["month"] == "2025-12"
        assert trend[0]["income"] == 0 and trend[0]["expense"] == 0
    finally:
        for record_id in ids:
            await client.delete(f"{BASE}/{record_id}")


async def test_ledger_year_stats(
    client: httpx.AsyncClient, site_user: dict, site_grant
):
    """年度统计(month=YYYY): 全年概览 + 分类饼图 + 全年12月趋势

    使用独立普通用户(临时授权 create/read/delete), 与管理员账户的
    历史遗留账目隔离, 保证合计精确断言
    """
    user_id = site_user["user_id"]
    headers = site_user["headers"]
    ids = []
    try:
        for act in ("create", "read", "delete"):
            await site_grant(user_id, "ledger", act)

        for payload in (
            {"amount": 5000, "flow_type": "income", "category": "工资", "occurred_at": "2026-03-05"},
            {"amount": 120.5, "flow_type": "expense", "category": "餐饮", "occurred_at": "2026-03-10"},
            {"amount": 50, "flow_type": "expense", "category": "交通", "occurred_at": "2026-08-02"},
        ):
            resp = await client.post(BASE, json=payload, headers=headers)
            assert resp.status_code == 201, resp.text
            ids.append(resp.json())

        resp = await client.get(f"{BASE}/stats", params={"month": "2026"}, headers=headers)
        assert resp.status_code == 200, resp.text
        stats = resp.json()

        # 概览: 收入5000 支出170.5 结余4829.5, 周期回显 YYYY
        assert stats["month"] == "2026"
        assert stats["income_total"] == 5000
        assert stats["expense_total"] == 170.5
        assert stats["balance"] == 4829.5

        # 饼图: 餐饮120.5排第一, 交通50在列
        pie = stats["category_pie"]
        assert pie[0]["category"] == "餐饮" and pie[0]["total"] == 120.5
        assert any(item["category"] == "交通" and item["total"] == 50 for item in pie)

        # 趋势: 全年12个月(2026-01 ~ 2026-12), 缺失月份补零
        trend = stats["trend"]
        assert len(trend) == 12
        assert trend[0]["month"] == "2026-01"
        assert trend[-1]["month"] == "2026-12"
        assert trend[2]["month"] == "2026-03"
        assert trend[2]["income"] == 5000 and trend[2]["expense"] == 120.5
        assert trend[7]["month"] == "2026-08" and trend[7]["expense"] == 50
        assert trend[0]["income"] == 0 and trend[0]["expense"] == 0
    finally:
        for record_id in ids:
            await client.delete(f"{BASE}/{record_id}", headers=headers)


async def test_ledger_stats_validation(client: httpx.AsyncClient):
    """参数校验: month 不满足 YYYY-MM / YYYY → 422"""
    for bad in ("2026-5", "2026-13", "26", "2026-001", "abc"):
        resp = await client.get(f"{BASE}/stats", params={"month": bad})
        assert resp.status_code == 422, f"{bad}: {resp.text}"


async def test_ledger_ownership_isolation(
    client: httpx.AsyncClient, site_user: dict, site_grant
):
    """归属隔离: 普通用户(已授权)看不到也改不了管理员的账目"""
    created_id = None
    user_id = site_user["user_id"]
    try:
        resp = await client.post(
            BASE,
            json={"amount": 999, "flow_type": "income", "category": "工资", "occurred_at": "2026-05-01"},
        )
        assert resp.status_code == 201, resp.text
        created_id = resp.json()

        # 授予普通用户 ledger 读/改权限(fixture 结束自动回收)
        await site_grant(user_id, "ledger", "read")
        await site_grant(user_id, "ledger", "update")

        # 普通用户统计中不包含管理员数据(自身无记录 → 全 0)
        resp = await client.get(
            f"{BASE}/stats", params={"month": "2026-05"}, headers=site_user["headers"]
        )
        assert resp.status_code == 200, resp.text
        stats = resp.json()
        assert stats["income_total"] == 0 and stats["expense_total"] == 0

        # 普通用户直接查询管理员记录 → 404
        resp = await client.get(f"{BASE}/{created_id}", headers=site_user["headers"])
        assert resp.status_code == 404, resp.text

        # 普通用户更新管理员记录 → 404
        resp = await client.put(
            f"{BASE}/{created_id}", json={"amount": 1}, headers=site_user["headers"]
        )
        assert resp.status_code == 404, resp.text
    finally:
        if created_id:
            await client.delete(f"{BASE}/{created_id}")


async def test_ledger_permission_denied(
    client: httpx.AsyncClient, site_user: dict, anon_client: httpx.AsyncClient
):
    """权限收紧: default_policies=[] → 普通用户 403, 匿名 401"""
    resp = await client.post(
        BASE, json={"amount": 1, "category": "测试"}, headers=site_user["headers"]
    )
    assert resp.status_code == 403, resp.text

    resp = await client.get(
        f"{BASE}/stats", params={"month": "2026-05"}, headers=site_user["headers"]
    )
    assert resp.status_code == 403, resp.text

    resp = await anon_client.get(f"{BASE}/list")
    assert resp.status_code == 401, resp.text
