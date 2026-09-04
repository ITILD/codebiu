# -*- coding: utf-8 -*-
"""module_rag/conversation 接口标准测试
覆盖: 创建会话/我的会话列表/详情/更新/消息列表(空)/删除/不存在会话
说明: 聊天流式端点(POST /rag/rag-chat/{id}/chat)依赖 LLM,不在本文件测试范围
"""

import time
import uuid

import httpx

BASE = "/rag/conversations"


def _make_conversation() -> dict:
    """构造唯一测试会话数据"""
    return {
        "title": f"测试会话_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
        "project_ids": [],  # 不关联知识库,避免触发检索
    }


async def test_conversation_crud_flow(client: httpx.AsyncClient):
    """创建会话→我的列表→详情→更新→消息列表→删除 全流程"""
    data = _make_conversation()
    resp = await client.post(BASE, json=data)
    assert resp.status_code == 201, resp.text
    conversation_id = resp.json()
    assert isinstance(conversation_id, str) and conversation_id, f"应返回会话ID: {resp.text}"
    deleted_ok = False
    try:
        # 我的会话列表应包含新会话
        resp = await client.get(f"{BASE}/my", params={"page": 1, "size": 50})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 1, "我的会话列表应非空"
        assert any(
            item["id"] == conversation_id for item in body["items"]
        ), "我的会话列表应包含新会话"

        # 查询详情
        resp = await client.get(f"{BASE}/{conversation_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["title"] == data["title"], "标题应一致"
        assert body["project_ids"] == [], "关联知识库应为空列表"

        # 更新标题(204)
        resp = await client.put(f"{BASE}/{conversation_id}", json={"title": "改名后的会话"})
        assert resp.status_code in (200, 204), resp.text

        # 验证更新生效
        resp = await client.get(f"{BASE}/{conversation_id}")
        assert resp.json()["title"] == "改名后的会话", "标题应已更新"

        # 消息列表(新会话应为空)
        resp = await client.get(
            f"{BASE}/{conversation_id}/messages", params={"page": 1, "size": 100}
        )
        assert resp.status_code == 200, resp.text
        assert isinstance(resp.json()["items"], list), "消息列表应返回数组"
    finally:
        # 删除会话(同时删除关联消息+checkpointer线程; checkpointer 清理失败已降级)
        resp = await client.delete(f"{BASE}/{conversation_id}")
        assert resp.status_code in (200, 204), resp.text
        deleted_ok = True

    # 删除成功后详情应 404(该端点正确透传 404)
    if deleted_ok:
        resp = await client.get(f"{BASE}/{conversation_id}")
        assert resp.status_code == 404, resp.text


async def test_conversation_not_found(client: httpx.AsyncClient):
    """查询不存在的会话应 404"""
    resp = await client.get(f"{BASE}/no-such-conversation-{uuid.uuid4().hex[:8]}")
    assert resp.status_code == 404, resp.text


async def test_conversation_create_with_project_ids(client: httpx.AsyncClient):
    """创建会话可携带关联知识库ID列表(不校验项目存在性,仅存储)"""
    fake_project_id = f"no-such-project-{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        BASE, json={"title": f"关联会话_{int(time.time() * 1000)}", "project_ids": [fake_project_id]}
    )
    assert resp.status_code == 201, resp.text
    conversation_id = resp.json()
    try:
        resp = await client.get(f"{BASE}/{conversation_id}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["project_ids"] == [fake_project_id], "关联ID应原样保存"
    finally:
        await client.delete(f"{BASE}/{conversation_id}")
