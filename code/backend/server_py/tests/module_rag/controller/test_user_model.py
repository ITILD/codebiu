# -*- coding: utf-8 -*-
"""module_rag/user_model 接口标准测试
覆盖: 查询我的绑定/更新绑定(合法/非法模型ID)/解绑/回退开关 fallback_disabled
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
    """绑定不存在的模型配置应 404(资源不存在语义)"""
    resp = await client.put(
        f"{BASE}/my", json={"chat_model_id": f"no-such-model-{uuid.uuid4().hex[:8]}"}
    )
    assert resp.status_code == 404, f"不存在的模型配置应 404: {resp.text}"


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


async def test_embedding_fallback_to_default_public(client: httpx.AsyncClient):
    """RAG 模型回退: 用户未绑定 embedding 模型时,
    get_llm_by_user_id 应回退到当前生效的默认公共向量化模型(启动 seed 提供)"""
    # 拿到当前登录用户(admin)的 user_id 并解绑 embedding
    resp = await client.get(f"{BASE}/my")
    assert resp.status_code == 200, resp.text
    user_id = resp.json()["user_id"]
    resp = await client.put(f"{BASE}/my", json={"embedding_model_id": None})
    assert resp.status_code == 200, resp.text

    from module_ai.utils.llm.types import ModelType
    from module_rag.service.user_model import UserModelService

    service = UserModelService()
    llm = await service.get_llm_by_user_id(user_id, False, ModelType.EMBEDDINGS)
    # get_llm 仅加载配置构建实例, 不会真实调用外部 API
    assert llm is not None, "未绑定向量化模型时应回退默认公共模型, 而不是返回 None"


async def test_chat_fallback_returns_none_without_default(client: httpx.AsyncClient, monkeypatch):
    """回退兜底: 用户未绑定且无生效默认公共模型时, get_llm_by_user_id 返回 None(不抛异常)"""
    resp = await client.get(f"{BASE}/my")
    assert resp.status_code == 200, resp.text
    user_id = resp.json()["user_id"]
    resp = await client.put(f"{BASE}/my", json={"chat_model_id": None})
    assert resp.status_code == 200, resp.text

    from module_ai.utils.llm.types import ModelType
    from module_rag.service import user_model as um

    service = um.UserModelService()
    # mock 掉 fallback 查询, 模拟"无生效默认公共模型"环境
    async def _no_fallback(model_type):
        return None
    monkeypatch.setattr(service, "_get_fallback_model_id", _no_fallback)
    llm = await service.get_llm_by_user_id(user_id, False, ModelType.CHAT)
    assert llm is None, "无绑定且无回退模型时应返回 None"


async def test_fallback_disabled_switch_persist(client: httpx.AsyncClient):
    """回退开关(v4 4.3): PUT /my 可切换 fallback_disabled 且 GET /my 能读回"""
    try:
        # 开启: 绑定失效不回退
        resp = await client.put(f"{BASE}/my", json={"fallback_disabled": True})
        assert resp.status_code == 200, resp.text
        assert resp.json()["fallback_disabled"] is True, "开启后应返回 True"

        resp = await client.get(f"{BASE}/my")
        assert resp.status_code == 200, resp.text
        assert resp.json()["fallback_disabled"] is True, "GET /my 应能读回开启状态"

        # 关闭: 恢复默认回退行为
        resp = await client.put(f"{BASE}/my", json={"fallback_disabled": False})
        assert resp.status_code == 200, resp.text
        assert resp.json()["fallback_disabled"] is False, "关闭后应返回 False"

        # 显式传 null 应被忽略(不解绑模型也不报 500)
        resp = await client.put(f"{BASE}/my", json={"fallback_disabled": None})
        assert resp.status_code == 200, f"显式 null 回退开关应被忽略: {resp.text}"
        assert resp.json()["fallback_disabled"] is False, "null 不应改变现有开关状态"
    finally:
        # 清理: 恢复默认(允许回退), 避免影响其他用例
        resp = await client.put(f"{BASE}/my", json={"fallback_disabled": False})
        assert resp.status_code == 200, resp.text


async def test_resolve_model_respects_fallback_disabled(client: httpx.AsyncClient, monkeypatch):
    """resolve_model 尊重用户回退开关(v4 4.3): 关闭回退时绑定失效返回 None 且不触发 fallback;
    开启回退时返回默认公共模型并标记 fallback_used=True"""
    resp = await client.get(f"{BASE}/my")
    assert resp.status_code == 200, resp.text
    user_id = resp.json()["user_id"]

    from module_ai.utils.llm.types import ModelType
    from module_rag.service import user_model as um

    service = um.UserModelService()

    # mock fallback 查询返回固定 ID, 用于证明"是否触发了回退"
    async def _fake_fallback(model_type):
        return "fake-default-model-id"

    monkeypatch.setattr(service, "_get_fallback_model_id", _fake_fallback)

    # 解绑 chat + 关闭回退: 绑定失效不回退, model_id 为 None 且 fallback_used=False
    resp = await client.put(f"{BASE}/my", json={"chat_model_id": None, "fallback_disabled": True})
    assert resp.status_code == 200, resp.text
    resolved = await service.resolve_model(user_id, ModelType.CHAT)
    assert resolved.model_id is None, "关闭回退时绑定失效应返回 None"
    assert resolved.fallback_used is False, "未回退时 fallback_used 应为 False"

    # 开启回退: 回退默认公共模型且标记 fallback_used=True(兜底链可感知)
    resp = await client.put(f"{BASE}/my", json={"fallback_disabled": False})
    assert resp.status_code == 200, resp.text
    resolved = await service.resolve_model(user_id, ModelType.CHAT)
    assert resolved.model_id == "fake-default-model-id", "开启回退时应回退默认公共模型"
    assert resolved.fallback_used is True, "发生回退时 fallback_used 应为 True"
