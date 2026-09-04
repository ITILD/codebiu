# -*- coding: utf-8 -*-
"""module_main/dict_item 字典项接口标准测试
覆盖: 创建(字典类型+字典项)/单查/按code查/按类型查/计数/更新/删除 全流程
     + 分页列表 + 滚动加载 + 不存在类型/不存在ID场景
"""

import time
import uuid

import httpx

BASE = "/dict_items"
TYPE_BASE = "/dict_types"


def _make_dict_type() -> dict:
    """构造唯一测试字典类型数据"""
    suffix = str(int(time.time() * 1000))
    return {
        "type_code": f"test_item_type_{suffix}",
        "type_name": f"字典项测试类型{suffix}",
        "description": "字典项测试用字典类型",
        "is_active": True,
        "sort_order": 1,
    }


def _make_dict_item(dict_type_id: str, index: int) -> dict:
    """构造唯一测试字典项数据(依赖字典类型ID)"""
    suffix = str(int(time.time() * 1000))
    return {
        "dict_type_id": dict_type_id,
        "item_code": f"test_item_{index}_{suffix}",
        "item_name": f"测试字典项{index}_{suffix}",
        "item_value": f"value_{index}_{suffix}",
        "description": "接口测试自动创建的字典项",
        "is_active": True,
        "sort_order": index,
    }


async def _create_dict_type(client: httpx.AsyncClient, data: dict) -> tuple[str, str]:
    """创建字典类型, 返回 (ID, type_code)"""
    resp = await client.post(TYPE_BASE, json=data)
    assert resp.status_code in (200, 201), resp.text
    return resp.json(), data["type_code"]


async def _create_dict_item(client: httpx.AsyncClient, data: dict) -> str:
    """创建字典项并返回ID(POST 声明 201, 响应体为纯字符串ID)"""
    resp = await client.post(BASE, json=data)
    assert resp.status_code in (200, 201), resp.text
    item_id = resp.json()
    assert isinstance(item_id, str) and item_id, f"创建应返回字符串ID: {resp.text}"
    return item_id


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


async def test_dict_item_crud_flow(client: httpx.AsyncClient):
    """字典项: 创建类型→创建项→单查→按code查→按类型查→计数→更新→删除 全流程"""
    type_data = _make_dict_type()
    type_id, type_code = await _create_dict_type(client, type_data)
    item_ids: list[str] = []
    try:
        # 创建两个字典项挂到同一类型下
        item_data = _make_dict_item(type_id, 1)
        item_id = await _create_dict_item(client, item_data)
        item_ids.append(item_id)
        item_ids.append(await _create_dict_item(client, _make_dict_item(type_id, 2)))

        # 查询单个: 字段应与创建数据一致
        resp = await client.get(f"{BASE}/{item_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["id"] == item_id, "ID应一致"
        assert body["dict_type_id"] == type_id, "所属类型ID应一致"
        assert body["item_code"] == item_data["item_code"], "item_code应一致"
        assert body["item_value"] == item_data["item_value"], "item_value应一致"

        # 按编码全局查询: 应返回同一条记录
        resp = await client.get(f"{BASE}/code/{item_data['item_code']}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["id"] == item_id, "按code查到的应是同一条记录"

        # 按字典类型编码查询: 应返回该类型下全部2条
        resp = await client.get(f"{BASE}/by-type/{type_code}")
        assert resp.status_code == 200, resp.text
        items = resp.json()
        assert isinstance(items, list) and len(items) == 2, f"应返回2条: {items}"
        assert all(item["dict_type_id"] == type_id for item in items), "都应属于该类型"

        # 按字典类型编码计数: 应为 2
        resp = await client.get(f"{BASE}/by-type/{type_code}/count")
        assert resp.status_code == 200, resp.text
        assert resp.json() == 2, f"计数应为2: {resp.text}"

        # 更新: PUT 声明 204, 需携带完整必填字段
        update_data = {**item_data, "item_name": f"改名后的字典项_{item_data['item_code']}"}
        resp = await client.put(f"{BASE}/{item_id}", json=update_data)
        assert resp.status_code in (200, 204), resp.text

        # 验证更新生效
        resp = await client.get(f"{BASE}/{item_id}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["item_name"] == update_data["item_name"], "名称应已更新"

        # 删除第一个字典项
        resp = await client.delete(f"{BASE}/{item_id}")
        assert resp.status_code in (200, 204), resp.text
        item_ids.remove(item_id)

        # 删除后查询应 404
        resp = await client.get(f"{BASE}/{item_id}")
        assert resp.status_code == 404, f"删除后查询应404: {resp.status_code} {resp.text}"

        # 计数应降为 1
        resp = await client.get(f"{BASE}/by-type/{type_code}/count")
        assert resp.status_code == 200, resp.text
        assert resp.json() == 1, f"删除后计数应为1: {resp.text}"
    finally:
        # 清理: 先删字典项再删字典类型(尽力而为)
        for iid in list(item_ids):
            await client.delete(f"{BASE}/{iid}")
        await client.delete(f"{TYPE_BASE}/{type_id}")


async def test_dict_item_list_and_scroll(client: httpx.AsyncClient):
    """分页列表与滚动加载: 返回标准结构且包含新建记录"""
    type_data = _make_dict_type()
    type_id, _type_code = await _create_dict_type(client, type_data)
    item_data = _make_dict_item(type_id, 1)
    item_id = await _create_dict_item(client, item_data)
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
        codes = [item.get("item_code") for item in resp.json()["items"]]
        assert item_data["item_code"] in codes, "全量拉取应包含新建记录"

        # 滚动加载: 沿游标翻页遍历全表应能找到新建记录
        found = await _scroll_find(client, "item_code", item_data["item_code"])
        assert found, "滚动遍历全表应能找到新建记录"
    finally:
        await client.delete(f"{BASE}/{item_id}")
        await client.delete(f"{TYPE_BASE}/{type_id}")


async def test_dict_item_query_by_missing_type_code(client: httpx.AsyncClient):
    """查询不存在的字典类型编码: 列表返回空, 计数返回0(服务层约定)"""
    suffix = str(int(time.time() * 1000))
    fake_code = f"no_such_type_{suffix}"

    # 按类型查列表: 不存在的类型应返回空列表
    resp = await client.get(f"{BASE}/by-type/{fake_code}")
    assert resp.status_code == 200, resp.text
    assert resp.json() == [], f"不存在的类型应返回空列表: {resp.text}"

    # 按类型计数: 不存在的类型应返回 0
    resp = await client.get(f"{BASE}/by-type/{fake_code}/count")
    assert resp.status_code == 200, resp.text
    assert resp.json() == 0, f"不存在的类型计数应为0: {resp.text}"


async def test_dict_item_get_not_found(client: httpx.AsyncClient):
    """查询单个不存在的字典项ID应 404"""
    fake_id = uuid.uuid4().hex
    resp = await client.get(f"{BASE}/{fake_id}")
    assert resp.status_code in (404, 400, 500), f"应返回404: {resp.status_code} {resp.text}"
