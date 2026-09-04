# -*- coding: utf-8 -*-
"""module_rag/user_model 接口标准测试
覆盖: 查询我的绑定/更新绑定(合法/非法模型ID)/解绑
说明: 绑定前会校验模型配置归属(本人或已共享),因此用 /ai/model-configs 创建本人配置来测合法分支
"""

import time
import uuid

import httpx

BASE = "/rag/user-models"
AI_MODEL_BASE = "/ai/model-configs"


def _make_model_config() -> dict:
    """构造测试用模型配置(归属当前登录用户,不会真实调用)"""
    return {
        "model_type": "chat",
        "server_type": "openai",
        "model": f"test-chat-model-{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
        "api_key": "test-not-a-real-key",
        "is_public": False,
    }


async def test_get_my_binding_default(client: httpx.AsyncClient):
    """查询当前用户绑定: 应返回包含 user_id 的绑定结构(未绑定为空值)"""
    resp = await client.get(f"{BASE}/my")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user_id"], "应返回当前登录用户ID"
    for field in ("chat_model_id", "embedding_model_id", "rerank_model_id"):
        assert field in body, f"响应应包含字段 {field}: {body}"


async def test_update_binding_unknown_model_rejected(client: httpx.AsyncClient):
    """绑定不存在的模型配置应 400"""
    resp = await client.put(
        f"{BASE}/my", json={"chat_model_id": f"no-such-model-{uuid.uuid4().hex[:8]}"}
    )
    assert resp.status_code == 400, f"不存在的模型配置应 400: {resp.text}"


async def test_binding_upsert_flow(client: httpx.AsyncClient):
    """创建本人模型配置→绑定→查询生效→解绑 全流程"""
    # 前置: 创建一个归属 admin 本人的模型配置
    cfg = _make_model_config()
    resp = await client.post(AI_MODEL_BASE, json=cfg)
    assert resp.status_code == 201, resp.text
    model_id = resp.json()
    assert isinstance(model_id, str) and model_id, f"应返回模型配置ID: {resp.text}"

    try:
        # 绑定 chat 模型
        resp = await client.put(f"{BASE}/my", json={"chat_model_id": model_id})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["chat_model_id"] == model_id, "绑定后应返回新的模型ID"
        assert body["user_id"], "响应应携带 user_id"

        # 查询校验绑定已生效
        resp = await client.get(f"{BASE}/my")
        assert resp.status_code == 200, resp.text
        assert resp.json()["chat_model_id"] == model_id, "GET /my 应能查到绑定"

        # 再次 PUT 覆盖绑定(upsert 更新分支)
        resp = await client.put(f"{BASE}/my", json={"embedding_model_id": model_id})
        assert resp.status_code == 200, resp.text

        # 解绑: 置空全部字段
        resp = await client.put(
            f"{BASE}/my",
            json={"chat_model_id": None, "embedding_model_id": None, "rerank_model_id": None},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["chat_model_id"] is None and body["embedding_model_id"] is None, "解绑后应为空"
    finally:
        # 清理: 删除测试模型配置
        resp = await client.delete(f"{AI_MODEL_BASE}/{model_id}")
        assert resp.status_code in (200, 204), resp.text
