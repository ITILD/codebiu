# -*- coding: utf-8 -*-
"""module_rag/project-document-chunks 重向量化接口标准测试
覆盖: 非管理员 403 / 管理员提交任务返回 task_id / 状态查询结构
说明: 真实 Milvus 全量重算与 embedding 调用依赖外部服务, 按约定不在接口测试中执行
(任务主体 _revectorize_chunks 由 worker 消费, memory broker 下提交后保持 PENDING)
"""

import httpx

BASE = "/rag/project-document-chunks"


async def test_revectorize_forbidden_for_non_admin(user_client: httpx.AsyncClient):
    """非管理员提交全库重向量化应 403"""
    resp = await user_client.post(f"{BASE}/revectorize", json={})
    assert resp.status_code == 403, f"非管理员应 403: {resp.text}"

    # 状态查询同样受限
    resp = await user_client.get(f"{BASE}/revectorize/status/some-task-id")
    assert resp.status_code == 403, f"非管理员查询进度应 403: {resp.text}"


async def test_revectorize_admin_submit_and_status(client: httpx.AsyncClient):
    """管理员提交重向量化任务应返回 task_id, 且状态查询接口可访问"""
    resp = await client.post(f"{BASE}/revectorize", json={})
    assert resp.status_code == 202, resp.text
    body = resp.json()
    task_id = body.get("task_id")
    assert task_id, f"应返回 Celery 任务ID: {body}"

    # 查询任务状态(memory broker 下任务未被 worker 消费, 应为 PENDING 等中间态)
    resp = await client.get(f"{BASE}/revectorize/status/{task_id}")
    assert resp.status_code == 200, resp.text
    status = resp.json()
    assert status["task_id"] == task_id, "状态响应应回显任务ID"
    assert "state" in status, f"状态响应应包含 state 字段: {status}"


async def test_revectorize_request_validation(client: httpx.AsyncClient):
    """请求体校验: 非法字段类型应 422(model_id 需为字符串或 null)"""
    resp = await client.post(f"{BASE}/revectorize", json={"model_id": 12345})
    assert resp.status_code == 422, f"非法 model_id 类型应 422: {resp.text}"
