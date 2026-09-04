# -*- coding: utf-8 -*-
"""module_geometry/feature 接口标准测试
覆盖: 创建/查询/更新/删除 全流程、列表过滤(名称/类型)、全量查询、
GeoJSON 参数校验、权限保护(admin 穿透 + 匿名拒绝)

模块子应用挂载于 /geometry(由 src/app.py 导入 feature 控制器),
style 字段为前端自定义渲染样式 JSON(含 style.height 等嵌套结构)。
"""

import time

import httpx
import pytest

BASE = "/geometry/features"

# 合理样例数据: GeoJSON 点 + 渲染样式(含嵌套 style.height)
POINT_GEO = {"type": "Point", "coordinates": [116.397, 39.908]}
STYLE_SAMPLE = {
    "color": "#FF4D4F",
    "opacity": 0.8,
    "width": 2,
    "style": {"height": 120, "extruded": True},
}


def _suffix() -> str:
    """时间戳唯一后缀, 避免重复执行/并发时数据串扰"""
    return str(int(time.time() * 1000))


async def test_feature_crud_flow(client: httpx.AsyncClient):
    """创建→查询→更新→删除 全流程(点→线重绘, style/properties 回显)"""
    suffix = _suffix()
    name = f"测试点_{suffix}"
    created_id = None
    try:
        # 创建(Point + style JSON)
        resp = await client.post(
            BASE,
            json={
                "name": name,
                "geometry": POINT_GEO,
                "properties": {"desc": "接口测试点"},
                "style": STYLE_SAMPLE,
            },
        )
        assert resp.status_code == 201, resp.text
        created_id = resp.json()
        assert isinstance(created_id, str) and created_id, f"创建应返回ID字符串: {created_id}"

        # 查询单个(geometry 以 GeoJSON 返回)
        resp = await client.get(f"{BASE}/{created_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["name"] == name
        assert body["feature_type"] == "point", "feature_type 应由 geometry.type 小写推导"
        assert body["style"] == STYLE_SAMPLE, "style JSON 应原样回显"
        assert body["properties"] == {"desc": "接口测试点"}, "properties 应原样回显"
        assert body["user_id"], "应返回创建者用户ID"
        geo = body["geometry"]
        assert geo["type"] == "Point"
        lon, lat = geo["coordinates"]
        assert lon == pytest.approx(116.397, abs=1e-6)
        assert lat == pytest.approx(39.908, abs=1e-6)

        # 更新(改名并重绘为线)
        new_name = f"改名线_{suffix}"
        line_geo = {
            "type": "LineString",
            "coordinates": [[116.39, 39.90], [116.40, 39.91]],
        }
        resp = await client.put(
            f"{BASE}/{created_id}", json={"name": new_name, "geometry": line_geo}
        )
        assert resp.status_code in (200, 204), resp.text

        # 验证更新生效(类型随 geometry 重绘变为 linestring)
        resp = await client.get(f"{BASE}/{created_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["name"] == new_name, "名称应已更新"
        assert body["feature_type"] == "linestring", "重绘后类型应为 linestring"
        assert body["geometry"]["type"] == "LineString"

        # 删除
        deleted_id = created_id
        created_id = None
        resp = await client.delete(f"{BASE}/{deleted_id}")
        assert resp.status_code in (200, 204), resp.text

        # 删除后查询应 404
        resp = await client.get(f"{BASE}/{deleted_id}")
        assert resp.status_code == 404, resp.text
    finally:
        # 兜底清理, 保证不依赖执行顺序
        if created_id:
            await client.delete(f"{BASE}/{created_id}")


async def test_feature_list_filter(client: httpx.AsyncClient):
    """分页列表: keyword 名称模糊 + feature_type 类型过滤"""
    suffix = _suffix()
    name = f"测试面_{suffix}"
    created_id = None
    try:
        polygon = {
            "type": "Polygon",
            "coordinates": [[[116.30, 39.85], [116.45, 39.85], [116.45, 39.95], [116.30, 39.85]]],
        }
        resp = await client.post(BASE, json={"name": name, "geometry": polygon})
        assert resp.status_code == 201, resp.text
        created_id = resp.json()

        resp = await client.get(
            f"{BASE}/list",
            params={"page": 1, "size": 10, "keyword": name, "feature_type": "polygon"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        for key in ("items", "total", "page", "size", "pages"):
            assert key in body, f"分页响应缺少字段 {key}: {body}"
        assert body["total"] >= 1, "过滤结果总数应至少为 1"
        assert any(item["name"] == name for item in body["items"]), "过滤结果应包含刚创建的要素"
        assert all(item["feature_type"] == "polygon" for item in body["items"]), "类型过滤应精确"
    finally:
        if created_id:
            await client.delete(f"{BASE}/{created_id}")


async def test_feature_list_all(client: httpx.AsyncClient):
    """全量查询(地球场景一次性渲染): 返回要素列表"""
    resp = await client.get(f"{BASE}/all")
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list), "/all 应返回列表"


async def test_feature_get_not_found(client: httpx.AsyncClient):
    """查询不存在的要素 → 404"""
    resp = await client.get(f"{BASE}/not-exist-{_suffix()}")
    assert resp.status_code == 404, resp.text


async def test_feature_delete_not_found(client: httpx.AsyncClient):
    """删除不存在的要素: dao ValueError → 404"""
    resp = await client.delete(f"{BASE}/not-exist-{_suffix()}")
    assert resp.status_code == 404, resp.text


async def test_feature_invalid_geometry(client: httpx.AsyncClient):
    """创建不支持的几何类型: 服务层 ValueError → 400"""
    resp = await client.post(
        BASE,
        json={
            "name": f"坏几何_{_suffix()}",
            "geometry": {"type": "Triangle", "coordinates": [[116.3, 39.8]]},
        },
    )
    assert resp.status_code == 400, resp.text


async def test_feature_invalid_type_filter(client: httpx.AsyncClient):
    """列表类型过滤传非法值: 服务层 ValueError → 400"""
    resp = await client.get(
        f"{BASE}/list", params={"page": 1, "size": 10, "feature_type": "triangle"}
    )
    assert resp.status_code == 400, resp.text


async def test_feature_unauthorized(anon_client: httpx.AsyncClient):
    """无鉴权访问受权限保护的端点 → 401/403"""
    resp = await anon_client.post(
        BASE, json={"name": "未授权", "geometry": POINT_GEO}
    )
    assert resp.status_code in (401, 403), resp.text
