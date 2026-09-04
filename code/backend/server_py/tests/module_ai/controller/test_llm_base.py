# -*- coding: utf-8 -*-
"""module_ai/llm_base 接口标准测试
只测配置校验分支: POST /check-config 与 POST /check-config-by-model-id
不测 /chat(需真实LLM服务),所有用例均不发起真实外部LLM网络请求。

安全分支说明(源码 src/module_ai/service/llm_base.py):
- model_type=rerank/ocr/asr/tts: 走"不支持的模型类型"分支,直接返回默认失败响应,不调用LLM
- model_type=chat + server_type=vllm: VLLM 方案未实现,_llm_by_config 返回 None,
  连通性校验触发异常被兜底捕获为校验失败,不发真实请求
- 不存在的 model_id: 服务层查库返回 None,直接返回校验失败,不调用LLM

注意: app.py 目前仅导入 model_config 控制器,llm_base 路由未随应用注册(见测试报告),
此处显式导入控制器模块以完成路由注册后再发起请求。
"""

import time
import uuid

import httpx

# 显式导入以注册路由(生产 app.py 未导入该控制器)
from module_ai.controller import llm_base  # noqa: F401

BASE = "/ai/llm-base"


def _make_check_body(model_type: str = "chat", server_type: str = "vllm") -> dict:
    """构造唯一配置校验请求体(默认 chat+vllm 组合不触发真实LLM调用)"""
    suffix = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    return {
        "model_type": model_type,
        "server_type": server_type,
        "model": f"test_model_{suffix}",
        "api_key": "test-key-not-real",
    }


async def test_check_config_unsupported_model_type(client: httpx.AsyncClient):
    """rerank 类型走"不支持的模型类型"分支: 返回默认失败响应,不触达真实LLM"""
    resp = await client.post(
        f"{BASE}/check-config", json=_make_check_body("rerank", "openai")
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_valid"] is False, "未实现的模型类型应校验失败"
    assert body["is_format"] is False, "未实现的模型类型不应支持格式化"


async def test_check_config_chat_chain_not_built(client: httpx.AsyncClient):
    """chat+vllm: LLM链构建为None,连通性校验异常兜底为校验失败,不发真实请求"""
    resp = await client.post(
        f"{BASE}/check-config", json=_make_check_body("chat", "vllm")
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_valid"] is False, "未实现的vllm方案应校验失败"


async def test_check_config_param_validation(client: httpx.AsyncClient):
    """配置校验参数校验: 非法枚举值应 422"""
    # 非法 server_type
    resp = await client.post(
        f"{BASE}/check-config", json=_make_check_body("chat", "not_a_server")
    )
    assert resp.status_code == 422, resp.text

    # 非法 model_type
    resp = await client.post(
        f"{BASE}/check-config", json=_make_check_body("no_such_type", "openai")
    )
    assert resp.status_code == 422, resp.text

    # 缺少必填的 model 字段
    resp = await client.post(
        f"{BASE}/check-config", json={"model_type": "chat", "server_type": "vllm"}
    )
    assert resp.status_code == 422, resp.text


async def test_check_config_by_model_id_not_exist(client: httpx.AsyncClient):
    """不存在的模型ID: 服务层返回False(不调用LLM),返回失败文案"""
    resp = await client.post(
        f"{BASE}/check-config-by-model-id",
        params={"model_id": f"nonexistent-model-{int(time.time() * 1000)}"},
    )
    assert resp.status_code == 200, resp.text
    assert "配置校验失败" in resp.json()["message"], "不存在的模型应返回校验失败文案"


async def test_check_config_by_model_id_missing_param(client: httpx.AsyncClient):
    """缺少 model_id 查询参数应 422"""
    resp = await client.post(f"{BASE}/check-config-by-model-id")
    assert resp.status_code == 422, resp.text


async def test_check_config_by_model_id_with_existing_config(client: httpx.AsyncClient):
    """真实存在但方案未实现的配置(vllm+chat): 走完整校验链路,兜底返回校验失败"""
    suffix = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    data = {
        "model_type": "chat",
        "server_type": "vllm",  # 未实现方案,校验兜底失败且不发真实请求
        "model": f"test_model_{suffix}",
        "api_key": "test-key-not-real",
    }
    config_id: str | None = None
    try:
        # 借助 model_config 端点创建测试配置
        resp = await client.post("/ai/model-configs", json=data)
        assert resp.status_code == 201, resp.text
        config_id = resp.json()

        # 按 model_id 校验配置
        resp = await client.post(
            f"{BASE}/check-config-by-model-id", params={"model_id": config_id}
        )
        assert resp.status_code == 200, resp.text
        assert "配置校验失败" in resp.json()["message"], "vllm方案未实现应校验失败"
    finally:
        # 清理测试配置
        if config_id:
            resp = await client.delete(f"/ai/model-configs/{config_id}")
            assert resp.status_code in (200, 204, 404), resp.text
