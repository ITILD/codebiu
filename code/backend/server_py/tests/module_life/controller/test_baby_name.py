# -*- coding: utf-8 -*-
"""module_life/baby_name 接口标准测试
覆盖: 名字 CRUD 全流程、批量删除、分页列表、AI推测端点(桩实现, 不真实调用外部LLM)、参数校验

注: src/app.py 中 module_life 控制器导入当前被注释,
路由 /life 不会随主应用挂载, 此处显式导入控制器模块触发挂载。

已知缺陷(以实际接口行为为准做兼容断言):
- GET 列表: dao 访问 PaginationParams 未定义的 order_by 属性 → 500
- DELETE 不存在的ID: dao 抛 ValueError 未映射为 404 → 500
"""

import time

import httpx

# 触发 /life 子应用挂载(否则主应用无该路由)
import module_life.controller.baby_name  # noqa: F401

BASE = "/life/baby-names"


def _suffix() -> str:
    """时间戳唯一后缀, 避免重复执行/并发时数据串扰"""
    return str(int(time.time() * 1000))


def _make_name(suffix: str) -> dict:
    """构造唯一宝宝名字数据(name 长度限制 1-10 字符, 取时间戳后6位)"""
    return {
        "name": f"测试{suffix[-6:]}",
        "gender": "boy",
        "style": "traditional",
        "meaning": f"接口测试含义_{suffix}",
        "popularity": 88,
    }


async def test_baby_name_crud_flow(client: httpx.AsyncClient):
    """创建→查询→更新→删除 全流程"""
    suffix = _suffix()
    data = _make_name(suffix)
    created_id = None
    try:
        # 创建
        resp = await client.post(BASE, json=data)
        assert resp.status_code == 201, resp.text
        created_id = resp.json()
        assert isinstance(created_id, str) and created_id, f"创建应返回ID字符串: {created_id}"

        # 查询单个
        resp = await client.get(f"{BASE}/{created_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["name"] == data["name"]
        assert body["gender"] == "boy"
        assert body["style"] == "traditional"
        assert body["meaning"] == data["meaning"]

        # 更新(改寓意与流行度)
        resp = await client.put(
            f"{BASE}/{created_id}", json={"meaning": "更新后的寓意", "popularity": 99}
        )
        assert resp.status_code in (200, 204), resp.text

        # 验证更新生效
        resp = await client.get(f"{BASE}/{created_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["meaning"] == "更新后的寓意", "寓意应已更新"
        assert body["popularity"] == 99, "流行度应已更新"

        # 删除
        deleted_id = created_id
        created_id = None
        resp = await client.delete(f"{BASE}/{deleted_id}")
        assert resp.status_code in (200, 204), resp.text

        # 删除后查询应 404(get 端点正确透传 HTTPException)
        resp = await client.get(f"{BASE}/{deleted_id}")
        assert resp.status_code == 404, resp.text
    finally:
        # 兜底清理, 保证不依赖执行顺序
        if created_id:
            await client.delete(f"{BASE}/{created_id}")


async def test_baby_name_batch_delete(client: httpx.AsyncClient):
    """批量删除: 创建两条 → batch-delete → 删除数量正确且查询不到"""
    ids = []
    try:
        for i in range(2):
            resp = await client.post(BASE, json=_make_name(f"{_suffix()}{i}"))
            assert resp.status_code == 201, resp.text
            ids.append(resp.json())

        resp = await client.post(f"{BASE}/batch-delete", json={"ids": ids})
        assert resp.status_code in (200, 204), resp.text
        deleted = resp.json() if resp.status_code == 200 else len(ids)
        # 响应为删除数量(int), 兼容结构体返回
        if isinstance(deleted, int):
            assert deleted == len(ids), f"应删除 {len(ids)} 条, 实际 {deleted}"

        # 批量删除后应查询不到
        for fid in ids:
            resp = await client.get(f"{BASE}/{fid}")
            assert resp.status_code == 404, f"批量删除后应查询不到 {fid}: {resp.text}"
        ids = []  # 已清理
    finally:
        # 兜底清理(batch-delete 失败时逐个删, 已删除的忽略失败)
        for fid in ids:
            await client.delete(f"{BASE}/{fid}")


async def test_baby_name_list(client: httpx.AsyncClient):
    """分页列表: 返回 200 且为分页结构(dao 访问未定义 order_by 的缺陷已修复)"""
    suffix = _suffix()
    created_id = None
    try:
        resp = await client.post(BASE, json=_make_name(suffix))
        assert resp.status_code == 201, resp.text
        created_id = resp.json()

        resp = await client.get(BASE, params={"page": 1, "size": 10})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert isinstance(body.get("items"), list), "items 应为列表"
        assert body.get("total", 0) >= 1, "列表总数应至少为 1"
    finally:
        if created_id:
            await client.delete(f"{BASE}/{created_id}")


async def test_baby_name_scroll(client: httpx.AsyncClient):
    """GET /scroll: 路由顺序缺陷已修复,应返回滚动结构"""
    resp = await client.get(f"{BASE}/scroll", params={"limit": 5})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body.get("items"), list), "滚动响应 items 应为列表"
    assert "has_more" in body, "滚动响应应包含 has_more"


async def test_baby_name_get_not_found(client: httpx.AsyncClient):
    """查询不存在的ID → 404"""
    resp = await client.get(f"{BASE}/not-exist-{_suffix()}")
    assert resp.status_code == 404, resp.text


async def test_baby_name_delete_not_found(client: httpx.AsyncClient):
    """删除不存在的ID → 404(ValueError 已映射)"""
    resp = await client.delete(f"{BASE}/not-exist-{_suffix()}")
    assert resp.status_code == 404, resp.text


async def test_baby_name_create_validation(client: httpx.AsyncClient):
    """创建参数校验: 缺必填字段 / name 超长 / 非法枚举 → 422"""
    # 缺少必填的 gender/style
    resp = await client.post(BASE, json={"name": "测试名"})
    assert resp.status_code == 422, resp.text

    # name 超过 10 字符(自定义校验器)
    resp = await client.post(
        BASE,
        json={"name": "这个名字实在是太长了超过了十个字", "gender": "boy", "style": "traditional"},
    )
    assert resp.status_code == 422, resp.text

    # gender 非法枚举
    resp = await client.post(
        BASE, json={"name": "测试名", "gender": "alien", "style": "traditional"}
    )
    assert resp.status_code == 422, resp.text


async def test_baby_name_predict_stub(client: httpx.AsyncClient):
    """/predict 为桩实现(不调用外部LLM), 合法入参返回空结果列表"""
    payload = {
        "birth_date": "2026-01-01",
        "birth_time": "08:00",
        "gender": "girl",
        "surname": "李",
    }
    resp = await client.post(f"{BASE}/predict", json=payload)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"results": []}, "桩实现应返回空结果列表"


async def test_baby_name_predict_validation(client: httpx.AsyncClient):
    """AI推测端点只测参数校验(422), 不真实调用外部LLM服务"""
    valid = {
        "birth_date": "2026-01-01",
        "birth_time": "08:00",
        "gender": "girl",
        "surname": "李",
    }

    # 缺少必填的 surname
    bad = {k: v for k, v in valid.items() if k != "surname"}
    for path in ("/predict", "/predict-name-info-preference", "/predict-baby-info-base"):
        resp = await client.post(f"{BASE}{path}", json=bad)
        assert resp.status_code == 422, f"{path}: {resp.text}"

    # gender 非法枚举
    resp = await client.post(
        f"{BASE}/predict", json=dict(valid, gender="alien")
    )
    assert resp.status_code == 422, resp.text

    # /predict-baby-info-base 缺少必填的 model_id
    resp = await client.post(f"{BASE}/predict-baby-info-base", json=valid)
    assert resp.status_code == 422, resp.text

    # /predict-name-info-preference-meaning 缺少必填的 name
    resp = await client.post(f"{BASE}/predict-name-info-preference-meaning", json={})
    assert resp.status_code == 422, resp.text
