# -*- coding: utf-8 -*-
"""module_agent/agent_run 运行接口标准测试
覆盖: 运行(404/私有 403/公共模型不存在 404)/运行历史(空/仅本人/404)
说明: 真实 LLM 调用属外部依赖, 按项目约定跳过; agent_run 落库链路由 service 单测外逻辑保证
"""

import uuid

import httpx
import pytest

BASE = "/agent/agents"
# 内置公共智能体(种子写入, 公共可运行, 用于测试通过访问校验后的分支)
BUILTIN_AGENT_ID = "builtin-agent-translator"


def _make_agent(name_suffix: str, **extra) -> dict:
    """构造测试用智能体创建请求(默认私有)"""
    return {
        "name": f"测试运行_{name_suffix}_{uuid.uuid4().hex[:6]}",
        "description": "运行接口测试智能体",
        "system_prompt": "你是一个测试智能体, 请将输入原样输出。",
        **extra,
    }


async def test_run_agent_not_found(client: httpx.AsyncClient):
    """运行不存在的智能体应 404"""
    resp = await client.post(
        f"{BASE}/{uuid.uuid4().hex}/run",
        json={"model_id": f"fake-model-{uuid.uuid4().hex[:6]}", "input": "hello"},
    )
    assert resp.status_code == 404, f"不存在的智能体应 404: {resp.text}"


async def test_run_private_agent_forbidden(user_client: httpx.AsyncClient, client: httpx.AsyncClient):
    """他人私有智能体不可运行(普通用户运行管理员创建的私有智能体应 403)"""
    data = _make_agent("private")
    resp = await client.post(BASE, json=data)
    assert resp.status_code == 201, resp.text
    agent_id = resp.json()

    try:
        resp = await user_client.post(
            f"{BASE}/{agent_id}/run",
            json={"model_id": f"fake-model-{uuid.uuid4().hex[:6]}", "input": "hello"},
        )
        assert resp.status_code == 403, f"他人私有智能体应 403: {resp.text}"
    finally:
        await client.delete(f"{BASE}/{agent_id}")


async def test_run_builtin_agent_model_not_found(client: httpx.AsyncClient):
    """公共(内置)智能体通过访问校验后, 模型配置不存在应 404"""
    resp = await client.post(
        f"{BASE}/{BUILTIN_AGENT_ID}/run",
        json={"model_id": f"no-such-model-{uuid.uuid4().hex[:8]}", "input": "hello"},
    )
    assert resp.status_code == 404, f"模型配置不存在应 404: {resp.text}"


@pytest.mark.skip(reason="依赖真实 LLM 网络调用(外部服务), 按项目约定跳过")
async def test_run_agent_with_real_llm(client: httpx.AsyncClient):
    """端到端运行: 真实模型执行 json→json 清洗并落历史(手动验证)"""
    ...


async def test_run_history_empty(client: httpx.AsyncClient):
    """运行历史: 未运行过时应返回空分页(结构含 items/total)"""
    data = _make_agent("history")
    resp = await client.post(BASE, json=data)
    assert resp.status_code == 201, resp.text
    agent_id = resp.json()

    try:
        resp = await client.get(f"{BASE}/{agent_id}/runs", params={"page": 1, "size": 10})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["items"] == [] and body["total"] == 0, f"应返回空历史: {body}"
    finally:
        await client.delete(f"{BASE}/{agent_id}")


async def test_run_history_agent_not_found(client: httpx.AsyncClient):
    """查询不存在智能体的运行历史应 404"""
    resp = await client.get(
        f"{BASE}/{uuid.uuid4().hex}/runs", params={"page": 1, "size": 10}
    )
    assert resp.status_code == 404, f"不存在的智能体应 404: {resp.text}"


async def test_run_history_only_mine(client: httpx.AsyncClient, user_client: httpx.AsyncClient):
    """运行历史仅本人可见: 普通用户查询管理员创建的智能体历史应为空(而非报错)"""
    data = _make_agent("mine-only")
    resp = await client.post(BASE, json=data)
    assert resp.status_code == 201, resp.text
    agent_id = resp.json()

    try:
        resp = await user_client.get(f"{BASE}/{agent_id}/runs", params={"page": 1, "size": 10})
        assert resp.status_code == 200, resp.text
        assert resp.json()["items"] == [], "他人查询应只见自己的空历史"
    finally:
        await client.delete(f"{BASE}/{agent_id}")
