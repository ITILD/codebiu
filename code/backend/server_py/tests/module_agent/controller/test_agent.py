# -*- coding: utf-8 -*-
"""module_agent/agent 管理接口标准测试
覆盖: 结构体字段(默认 str/str)创建与回读/JSON 结构体创建(含无 schema)/更新切回 str 清空结构
说明: 归属校验/内置不可删等原有用例语义不变, 本文件聚焦新增的结构体配置字段
"""

import uuid

import httpx

BASE = "/agent/agents"


def _make_agent(name_suffix: str, **extra) -> dict:
    """构造测试用智能体创建请求"""
    return {
        "name": f"测试智能体_{name_suffix}_{uuid.uuid4().hex[:6]}",
        "description": "结构体字段测试智能体",
        "system_prompt": "你是一个测试智能体, 用于验证结构体配置。",
        **extra,
    }


async def test_create_agent_default_str_io(client: httpx.AsyncClient):
    """默认创建: 不传结构体字段时应为 str 入/str 出且 schema 为空"""
    data = _make_agent("default")
    resp = await client.post(BASE, json=data)
    assert resp.status_code == 201, resp.text
    agent_id = resp.json()

    try:
        resp = await client.get(f"{BASE}/{agent_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["input_type"] == "str", f"默认输入类型应为 str: {body}"
        assert body["output_type"] == "str", f"默认输出类型应为 str: {body}"
        assert body["input_schema"] is None and body["output_schema"] is None
    finally:
        await client.delete(f"{BASE}/{agent_id}")


async def test_create_agent_with_struct_roundtrip(client: httpx.AsyncClient):
    """JSON 结构体创建→回读一致→更新切回 str 并清空结构 全流程"""
    input_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "姓名"},
            "age": {"type": "integer"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name"],
    }
    output_schema = {
        "type": "object",
        "properties": {"cleaned": {"type": "string"}, "score": {"type": "number"}},
        "required": ["cleaned"],
    }
    data = _make_agent(
        "struct",
        input_type="json",
        output_type="json",
        input_schema=input_schema,
        output_schema=output_schema,
    )
    resp = await client.post(BASE, json=data)
    assert resp.status_code == 201, resp.text
    agent_id = resp.json()

    try:
        # 回读: 结构体字段完整往返
        resp = await client.get(f"{BASE}/{agent_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["input_type"] == "json" and body["output_type"] == "json"
        assert body["input_schema"] == input_schema, f"输入结构应一致: {body}"
        assert body["output_schema"] == output_schema, f"输出结构应一致: {body}"

        # 更新: 切回字符串输入并清空输入结构(输出保持 json)
        resp = await client.put(
            f"{BASE}/{agent_id}",
            json={"input_type": "str", "input_schema": None},
        )
        assert resp.status_code == 204, resp.text
        resp = await client.get(f"{BASE}/{agent_id}")
        body = resp.json()
        assert body["input_type"] == "str" and body["input_schema"] is None
        assert body["output_type"] == "json" and body["output_schema"] == output_schema
    finally:
        await client.delete(f"{BASE}/{agent_id}")


async def test_create_agent_json_without_schema(client: httpx.AsyncClient):
    """input_type=json 但不提供 schema 也可创建(schema 可选, 运行时仅约束为合法 JSON)"""
    data = _make_agent("noschema", input_type="json", output_type="json")
    resp = await client.post(BASE, json=data)
    assert resp.status_code == 201, resp.text
    agent_id = resp.json()

    try:
        resp = await client.get(f"{BASE}/{agent_id}")
        body = resp.json()
        assert body["input_type"] == "json"
        assert body["input_schema"] is None and body["output_schema"] is None
    finally:
        await client.delete(f"{BASE}/{agent_id}")


async def test_agent_list_contains_struct_fields(client: httpx.AsyncClient):
    """列表项应携带结构体字段(前端渲染需要)"""
    resp = await client.get(BASE, params={"page": 1, "size": 5})
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    if items:
        for field in ("input_type", "output_type", "input_schema", "output_schema"):
            assert field in items[0], f"列表项应包含字段 {field}"
