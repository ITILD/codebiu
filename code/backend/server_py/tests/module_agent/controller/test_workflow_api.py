# -*- coding: utf-8 -*-
"""module_agent 工作流 API 测试
覆盖: 工作流保存端点(校验失败 400/成功 204/简单类型携带图 400)/运行分流(模板流成功含轨迹/
LLM 节点模型不存在 400 且失败落库)/运行详情(仅本人 404 语义)
说明: 不做真实 LLM 调用; 模板流(开始→模板→结束)全程无需模型即可跑通执行链路
"""

import uuid

import httpx

BASE = "/agent/agents"


def _make_agent(**extra) -> dict:
    """构造测试用工作流智能体创建请求(默认私有)"""
    return {
        "name": f"测试工作流_{uuid.uuid4().hex[:6]}",
        "description": "工作流接口测试智能体",
        "system_prompt": "你是测试智能体",
        "agent_type": "workflow",
        **extra,
    }


def _template_graph() -> dict:
    """合法最简模板流: 开始→模板(回显输入)→结束"""
    return {
        "nodes": [
            {"id": "s", "type": "start", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "t", "type": "template", "position": {"x": 100, "y": 0},
             "data": {"template": "回显: {{s}}"}},
            {"id": "e", "type": "end", "position": {"x": 200, "y": 0}, "data": {"result": "{{t}}"}},
        ],
        "edges": [
            {"id": "e1", "source": "s", "target": "t", "sourceHandle": None},
            {"id": "e2", "source": "t", "target": "e", "sourceHandle": None},
        ],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }


async def _create_workflow_agent(client: httpx.AsyncClient, **extra) -> str:
    """创建工作流智能体并返回ID"""
    resp = await client.post(BASE, json=_make_agent(**extra))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_save_workflow_invalid_graph_rejected(client: httpx.AsyncClient):
    """保存不合法工作流图应 400(缺结束节点)"""
    agent_id = await _create_workflow_agent(client)
    try:
        bad_graph = {
            "nodes": [{"id": "s", "type": "start", "position": {"x": 0, "y": 0}, "data": {}}],
            "edges": [],
        }
        resp = await client.put(
            f"{BASE}/{agent_id}/workflow", json={"agent_type": "workflow", "workflow": bad_graph}
        )
        assert resp.status_code == 400, f"不合法图应 400: {resp.text}"
        assert "结束节点" in resp.text, resp.text
    finally:
        await client.delete(f"{BASE}/{agent_id}")


async def test_save_workflow_simple_type_with_graph_rejected(client: httpx.AsyncClient):
    """简单类型携带工作流图应 400"""
    agent_id = await _create_workflow_agent(client, agent_type="simple")
    try:
        resp = await client.put(
            f"{BASE}/{agent_id}/workflow", json={"agent_type": "simple", "workflow": _template_graph()}
        )
        assert resp.status_code == 400, f"简单类型带图应 400: {resp.text}"
    finally:
        await client.delete(f"{BASE}/{agent_id}")


async def test_save_workflow_success_and_persisted(client: httpx.AsyncClient):
    """保存合法工作流图成功, 详情接口可读回类型与图"""
    agent_id = await _create_workflow_agent(client)
    try:
        resp = await client.put(
            f"{BASE}/{agent_id}/workflow", json={"agent_type": "workflow", "workflow": _template_graph()}
        )
        assert resp.status_code == 204, f"合法图应 204: {resp.text}"

        resp = await client.get(f"{BASE}/{agent_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["agent_type"] == "workflow", body
        assert body["workflow"]["nodes"], "工作流图应已落库"
    finally:
        await client.delete(f"{BASE}/{agent_id}")


async def test_run_workflow_template_flow(client: httpx.AsyncClient):
    """运行模板工作流: 无需模型即跑通, 返回结果与节点轨迹, 历史含 trace"""
    agent_id = await _create_workflow_agent(client)
    try:
        resp = await client.put(
            f"{BASE}/{agent_id}/workflow", json={"agent_type": "workflow", "workflow": _template_graph()}
        )
        assert resp.status_code == 204, resp.text

        resp = await client.post(
            f"{BASE}/{agent_id}/run", json={"model_id": "unused", "input": "你好工作流"}
        )
        assert resp.status_code == 200, f"模板流运行应 200: {resp.text}"
        body = resp.json()
        assert body["result"] == "回显: 你好工作流", body
        assert body["run_id"], "应返回运行记录ID"
        assert body["trace"] and len(body["trace"]) == 3, "应返回 3 个节点的执行轨迹"
        assert [t["node_type"] for t in body["trace"]] == ["start", "template", "end"]

        # 运行历史列表应携带 trace
        resp = await client.get(f"{BASE}/{agent_id}/runs", params={"page": 1, "size": 10})
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert len(items) == 1 and items[0]["trace"]["nodes"], f"历史应含轨迹: {items}"

        # 运行详情接口可查单条(含 trace)
        run_id = body["run_id"]
        resp = await client.get(f"{BASE}/{agent_id}/runs/{run_id}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["trace"]["nodes"], "运行详情应含轨迹"
    finally:
        await client.delete(f"{BASE}/{agent_id}")


async def test_run_workflow_llm_model_not_found_persists_failure(client: httpx.AsyncClient):
    """LLM 节点模型不存在: 运行 400, 失败轨迹落库可查"""
    graph = _template_graph()
    graph["nodes"].insert(
        1,
        {"id": "n", "type": "llm", "position": {"x": 50, "y": 0},
         "data": {"prompt": "处理 {{s}}", "output_type": "str"}},
    )
    graph["edges"] = [
        {"id": "e0", "source": "s", "target": "n", "sourceHandle": None},
        {"id": "e1", "source": "n", "target": "t", "sourceHandle": None},
        {"id": "e2", "source": "t", "target": "e", "sourceHandle": None},
    ]
    agent_id = await _create_workflow_agent(client)
    try:
        resp = await client.put(
            f"{BASE}/{agent_id}/workflow", json={"agent_type": "workflow", "workflow": graph}
        )
        assert resp.status_code == 204, resp.text

        resp = await client.post(
            f"{BASE}/{agent_id}/run", json={"model_id": f"no-such-{uuid.uuid4().hex[:6]}", "input": "x"}
        )
        assert resp.status_code == 400, f"模型不存在应 400: {resp.text}"

        # 失败运行也应落库(含 failed 轨迹)供排查
        resp = await client.get(f"{BASE}/{agent_id}/runs", params={"page": 1, "size": 10})
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert items and items[0]["output"].get("error"), f"失败记录应落库: {items}"
        assert any(t["status"] == "failed" for t in items[0]["trace"]["nodes"]), items
    finally:
        await client.delete(f"{BASE}/{agent_id}")


async def test_run_detail_only_owner_visible(client: httpx.AsyncClient, user_client: httpx.AsyncClient):
    """运行详情仅本人可见: 他人查询应 404"""
    agent_id = await _create_workflow_agent(client)
    try:
        resp = await client.put(
            f"{BASE}/{agent_id}/workflow", json={"agent_type": "workflow", "workflow": _template_graph()}
        )
        assert resp.status_code == 204, resp.text
        resp = await client.post(f"{BASE}/{agent_id}/run", json={"model_id": "unused", "input": "hi"})
        assert resp.status_code == 200, resp.text
        run_id = resp.json()["run_id"]

        resp = await user_client.get(f"{BASE}/{agent_id}/runs/{run_id}")
        assert resp.status_code == 404, f"他人查询运行详情应 404: {resp.text}"
    finally:
        await client.delete(f"{BASE}/{agent_id}")
