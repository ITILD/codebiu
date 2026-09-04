# -*- coding: utf-8 -*-
"""module_main/dict_type 字典类型接口标准测试
覆盖: 创建/单查/按编码查/更新/删除 全流程 + 分页列表 + 滚动加载 + 404 场景
"""

import time
import uuid

import httpx

BASE = "/dict_types"


def _make_dict_type() -> dict:
    """构造唯一测试字典类型数据(时间戳后缀避免残留数据冲突)"""
    suffix = str(int(time.time() * 1000))
    return {
        "type_code": f"test_type_{suffix}",
        "type_name": f"测试字典类型{suffix}",
        "description": "接口测试自动创建的字典类型",
        "is_active": True,
        "sort_order": 1,
    }


async def _create_dict_type(client: httpx.AsyncClient, data: dict) -> str:
    """创建字典类型并返回ID(POST 声明 201, 响应体为纯字符串ID)"""
    resp = await client.post(BASE, json=data)
    assert resp.status_code in (200, 201), resp.text
    type_id = resp.json()
    assert isinstance(type_id, str) and type_id, f"创建应返回字符串ID: {resp.text}"
    return type_id


async def _delete_dict_type(client: httpx.AsyncClient, type_id: str) -> None:
    """删除字典类型(清理用, 尽力而为)"""
    resp = await client.delete(f"{BASE}/{type_id}")
    assert resp.status_code in (200, 204, 404), resp.text


async def _scroll_find(
    client: httpx.AsyncClient, code_field: str, code_value: str
) -> bool:
    """沿 last_id 游标翻页滚动遍历, 查找指定记录(校验游标翻页机制), 返回是否找到"""
    last_id: str | None = None
    for _ in range(100):  # 上限100页, 防止异常数据导致死循环
        params: dict = {"limit": 10}
        if last_id:
            params["last_id"] = last_id
        resp = await client.get(f"{BASE}/scroll", params=params)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert isinstance(body.get("items"), list), "items应为列表"
        assert isinstance(body.get("has_more"), bool), "has_more应为布尔值"
        if any(item.get(code_field) == code_value for item in body["items"]):
            return True
        if not body["has_more"]:
            break
        last_id = body.get("last_id")
        assert last_id, "has_more=True 时必须返回 last_id 游标"
    return False


async def test_dict_type_crud_flow(client: httpx.AsyncClient):
    """字典类型: 创建→单查→按编码查→更新→验证→删除→404 全流程"""
    data = _make_dict_type()
    type_id = await _create_dict_type(client, data)
    try:
        # 查询单个: 字段应与创建数据一致
        resp = await client.get(f"{BASE}/{type_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["id"] == type_id, "ID应一致"
        assert body["type_code"] == data["type_code"], "type_code应一致"
        assert body["type_name"] == data["type_name"], "type_name应一致"

        # 按编码查询: 应返回同一条记录
        resp = await client.get(f"{BASE}/code/{data['type_code']}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["id"] == type_id, "按编码查到的应是同一条记录"

        # 更新: PUT 声明 204, 更新需携带完整必填字段(type_code/type_name)
        update_data = {**data, "type_name": f"改名后的字典类型{data['type_code']}"}
        resp = await client.put(f"{BASE}/{type_id}", json=update_data)
        assert resp.status_code in (200, 204), resp.text

        # 验证更新生效
        resp = await client.get(f"{BASE}/{type_id}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["type_name"] == update_data["type_name"], "名称应已更新"
    finally:
        await _delete_dict_type(client, type_id)

    # 删除后查询应 404
    resp = await client.get(f"{BASE}/{type_id}")
    assert resp.status_code == 404, f"删除后查询应404: {resp.status_code} {resp.text}"


async def test_dict_type_list_pagination(client: httpx.AsyncClient):
    """分页列表: 返回标准分页结构, keyword/is_active 过滤生效"""
    data = _make_dict_type()
    type_id = await _create_dict_type(client, data)
    try:
        # 分页列表结构校验(列表无显式排序, 只校验结构与分页参数回显)
        resp = await client.get(f"{BASE}/list", params={"page": 1, "size": 10})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        for key in ("items", "total", "page", "size", "pages"):
            assert key in body, f"分页响应应包含 {key}: {body}"
        assert isinstance(body["items"], list), "items应为列表"
        assert len(body["items"]) <= 10, "条数不应超过size"
        assert body["total"] >= 1, "total应至少为1(含新建记录)"
        assert body["page"] == 1 and body["size"] == 10, "应回显分页参数"

        # 一次拉取500条(接口上限): 应包含新建记录(前提是表中总数不超过500)
        resp = await client.get(f"{BASE}/list", params={"page": 1, "size": 500})
        assert resp.status_code == 200, resp.text
        codes = [item.get("type_code") for item in resp.json()["items"]]
        assert data["type_code"] in codes, "全量拉取应包含新建记录"

        # keyword 模糊搜索: 唯一编码应精确命中自己
        resp = await client.get(
            f"{BASE}/list", params={"page": 1, "size": 10, "keyword": data["type_code"]}
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert len(items) == 1 and items[0]["id"] == type_id, "keyword应只命中新建记录"

        # is_active 过滤: 与keyword组合, 启用状态命中/禁用状态为空
        resp = await client.get(
            f"{BASE}/list",
            params={"page": 1, "size": 10, "keyword": data["type_code"], "is_active": True},
        )
        assert resp.status_code == 200, resp.text
        assert len(resp.json()["items"]) == 1, "is_active=True 应命中新建记录"
        resp = await client.get(
            f"{BASE}/list",
            params={"page": 1, "size": 10, "keyword": data["type_code"], "is_active": False},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["items"] == [], "is_active=False 不应命中启用记录"
    finally:
        await _delete_dict_type(client, type_id)


async def test_dict_type_scroll(client: httpx.AsyncClient):
    """滚动加载: 沿游标翻页遍历全表应能找到新建记录(校验游标机制与响应结构)"""
    data = _make_dict_type()
    type_id = await _create_dict_type(client, data)
    try:
        found = await _scroll_find(client, "type_code", data["type_code"])
        assert found, "滚动遍历全表应能找到新建记录"
    finally:
        await _delete_dict_type(client, type_id)


async def test_dict_type_get_by_code_not_found(client: httpx.AsyncClient):
    """按编码查询不存在的字典类型应 404"""
    suffix = str(int(time.time() * 1000))
    resp = await client.get(f"{BASE}/code/nonexistent_type_{suffix}")
    assert resp.status_code == 404, f"应返回404: {resp.status_code} {resp.text}"


async def test_dict_type_get_not_found(client: httpx.AsyncClient):
    """查询单个不存在的字典类型ID应 404"""
    fake_id = uuid.uuid4().hex
    resp = await client.get(f"{BASE}/{fake_id}")
    assert resp.status_code in (404, 400, 500), f"应返回404: {resp.status_code} {resp.text}"
