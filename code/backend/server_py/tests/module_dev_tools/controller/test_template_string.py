# -*- coding: utf-8 -*-
"""module_dev_tools/template_string 模板字符串接口标准测试
覆盖: 创建/单查/更新/按ID渲染/删除 全流程 + 直接渲染 + 语法校验 + 列表/滚动 + 404 场景

注意: src/app.py 中 dev_tools 模块的导入被注释, 导致 /dev-tools 挂载不会注册;
此处显式导入控制器模块以触发 module_app 挂载与路由注册(见模块配置 config/server.py)。
"""

# 显式导入以注册 /dev-tools 挂载与模板字符串路由(生产代码 app.py 未导入该模块)
import module_dev_tools.controller.template_string  # noqa: F401
import time
import uuid

import httpx

BASE = "/dev-tools/template-strings"


def _make_template() -> dict:
    """构造唯一测试模板字符串数据(时间戳后缀避免残留数据冲突)"""
    suffix = str(int(time.time() * 1000))
    return {
        "name": f"测试模板{suffix}",
        "description": "接口测试自动创建的模板字符串",
        "template_content": "Hello ${name}, welcome to ${place}!",
        "category": "test",
        "tags": ["接口测试"],
        "is_active": True,
    }


async def _create_template(client: httpx.AsyncClient, data: dict) -> str:
    """创建模板字符串并返回ID(POST 声明 201, 响应体为纯字符串ID)"""
    resp = await client.post(BASE, json=data)
    assert resp.status_code in (200, 201), resp.text
    template_id = resp.json()
    assert isinstance(template_id, str) and template_id, f"创建应返回字符串ID: {resp.text}"
    return template_id


async def _scroll_find(
    client: httpx.AsyncClient, name_value: str
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
        if any(item.get("name") == name_value for item in body["items"]):
            return True
        if not body["has_more"]:
            break
        last_id = body.get("last_id")
        assert last_id, "has_more=True 时必须返回 last_id 游标"
    return False


async def test_template_string_crud_flow(client: httpx.AsyncClient):
    """模板字符串: 创建→单查→更新→验证→按ID渲染→删除→404 全流程"""
    data = _make_template()
    template_id = await _create_template(client, data)
    try:
        # 查询单个: 字段应与创建数据一致
        resp = await client.get(f"{BASE}/{template_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["id"] == template_id, "ID应一致"
        assert body["name"] == data["name"], "name应一致"
        assert body["template_content"] == data["template_content"], "模板内容应一致"

        # 更新: PUT 声明 204, 需携带完整必填字段(name/template_content)
        update_data = {
            **data,
            "name": f"改名后的模板_{data['name']}",
            "template_content": "Hi ${name}, your order is ${order_no}",
        }
        resp = await client.put(f"{BASE}/{template_id}", json=update_data)
        assert resp.status_code in (200, 204), resp.text

        # 验证更新生效
        resp = await client.get(f"{BASE}/{template_id}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["template_content"] == update_data["template_content"], (
            "模板内容应已更新"
        )

        # 按模板ID渲染: 变量齐全时应全部替换成功
        variables = {"name": "张三", "order_no": "A2024001"}
        resp = await client.post(
            f"{BASE}/render", json={"template_id": template_id, "variables": variables}
        )
        assert resp.status_code == 200, resp.text
        render_body = resp.json()
        assert render_body["rendered_content"] == "Hi 张三, your order is A2024001", (
            f"渲染结果不符: {render_body}"
        )
        assert sorted(render_body["variables_used"]) == ["name", "order_no"], (
            "应报告已使用的变量"
        )
        assert render_body["variables_missing"] == [], "变量齐全时缺失列表应为空"
    finally:
        resp = await client.delete(f"{BASE}/{template_id}")
        assert resp.status_code in (200, 204, 404), resp.text

    # 删除后查询应 404(404 被包装为 500 的缺陷已修复)
    resp = await client.get(f"{BASE}/{template_id}")
    assert resp.status_code == 404, f"删除后查询应404: {resp.status_code} {resp.text}"


async def test_template_string_render_direct(client: httpx.AsyncClient):
    """直接渲染: 传模板内容(不依赖数据库), 变量齐全时全部替换"""
    resp = await client.post(
        f"{BASE}/render",
        json={"template_content": "Hi ${who}", "variables": {"who": "tester"}},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rendered_content"] == "Hi tester", f"渲染结果不符: {body}"
    assert body["variables_used"] == ["who"], "应报告已使用的变量"
    assert body["variables_missing"] == [], "缺失变量列表应为空"

    # 变量缺失场景: 仍返回200, 但 missing 列表应报告缺失变量
    resp = await client.post(
        f"{BASE}/render",
        json={"template_content": "Hi ${who} and ${other}", "variables": {"who": "tester"}},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "other" in body["variables_missing"], f"应报告缺失变量: {body}"


async def test_template_string_validate(client: httpx.AsyncClient):
    """模板语法校验: template_content 为查询参数(裸 str 参数), 返回校验结果"""
    resp = await client.post(
        f"{BASE}/validate",
        params={"template_content": "Hello ${name}, welcome to ${place}!"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["valid"] is True, f"合法模板应校验通过: {body}"
    assert sorted(body["variables"]) == ["name", "place"], f"应提取出变量: {body}"


async def test_template_string_list_and_scroll(client: httpx.AsyncClient):
    """分页列表与滚动加载: 返回标准结构且包含新建记录"""
    data = _make_template()
    template_id = await _create_template(client, data)
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
        names = [item.get("name") for item in resp.json()["items"]]
        assert data["name"] in names, "全量拉取应包含新建记录"

        # 滚动加载: 沿游标翻页遍历全表应能找到新建记录
        found = await _scroll_find(client, data["name"])
        assert found, "滚动遍历全表应能找到新建记录"
    finally:
        await client.delete(f"{BASE}/{template_id}")


async def test_template_string_get_not_found(client: httpx.AsyncClient):
    """查询单个不存在的模板ID应 404(裸 except 吞 404 的缺陷已修复)"""
    fake_id = uuid.uuid4().hex
    resp = await client.get(f"{BASE}/{fake_id}")
    assert resp.status_code == 404, f"应返回404: {resp.status_code} {resp.text}"
