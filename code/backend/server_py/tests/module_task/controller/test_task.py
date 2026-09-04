# -*- coding: utf-8 -*-
"""module_task 任务队列接口标准测试
覆盖: 创建/详情/分页列表(含状态过滤)/统计/注册表/取消/同步/重试/删除/参数校验/404

约定:
- 不依赖 Celery worker 是否运行: 创建后任务可能停留 pending, 也可能被(共享 broker 上的)
  worker 立即取走转 running, 断言不等待 success、不针对瞬时活跃状态做过滤断言;
  排队中任务的取消正是本模块核心用途
- 每个用例内完成 创建→验证→取消/删除→清理, try/finally 保证不残留数据, 不依赖执行顺序
"""

import time
import uuid

import httpx

BASE = "/task/tasks"

# 注册表中真实可用的任务类型(见 module_task.tasks.TASK_TYPES)
TASK_TYPE = "demo_document"


def _suffix() -> str:
    """生成时间戳+随机唯一后缀, 保证任务名称可精确过滤且用例间互不干扰"""
    return f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"


def _make_task_data(suffix: str) -> dict:
    """构造唯一测试任务数据(payload 结构与注册表 default_payload 对齐)"""
    return {
        "name": f"接口测试任务_{suffix}",
        "task_type": TASK_TYPE,
        "payload": {
            "file_name": f"测试文档_{suffix}.pdf",
            "total_pages": 3,
            # 与注册表默认一致: 即使共享 broker 上有 worker 立即执行,
            # 也为 创建→取消 的测试序列保留足够窗口
            "duration": 16,
        },
        "priority": 0,
    }


async def _create_task(client: httpx.AsyncClient, data: dict) -> str:
    """创建任务并断言 201, 返回任务ID(创建端点 response_model=str, 直接返回ID字符串)"""
    resp = await client.post(BASE, json=data)
    assert resp.status_code == 201, resp.text
    task_id = resp.json()
    assert isinstance(task_id, str) and task_id, f"创建应返回任务ID字符串: {resp.text}"
    return task_id


async def _cleanup_task(client: httpx.AsyncClient, task_id: str) -> None:
    """兜底清理: 尽力删除任务(不存在则忽略), 不做断言以免掩盖原始失败"""
    await client.delete(f"{BASE}/{task_id}")


async def test_task_full_lifecycle(client: httpx.AsyncClient):
    """创建→详情→列表可见→取消→同步→删除→列表确认清理 全流程"""
    suffix = _suffix()
    data = _make_task_data(suffix)
    task_id = await _create_task(client, data)
    try:
        # 1. 详情: 字段应与创建数据一致, 初始为活跃态(无 worker 时停留 pending)
        resp = await client.get(f"{BASE}/{task_id}")
        assert resp.status_code == 200, resp.text
        detail = resp.json()
        assert detail["id"] == task_id
        assert detail["name"] == data["name"]
        assert detail["task_type"] == TASK_TYPE
        assert detail["payload"] == data["payload"]
        assert detail["status"] in ("pending", "running"), f"初始应为活跃态: {detail}"
        assert detail["progress"] == 0

        # 2. 列表: keyword 唯一后缀精确命中本次任务
        resp = await client.get(
            f"{BASE}/list", params={"page": 1, "size": 50, "keyword": suffix}
        )
        assert resp.status_code == 200, resp.text
        page = resp.json()
        assert page["total"] == 1, f"keyword 过滤应只命中本次任务: {page}"
        assert page["items"][0]["id"] == task_id

        # 3. 列表: task_type 过滤命中(与瞬时状态无关, 不受 worker 竞态影响)
        resp = await client.get(
            f"{BASE}/list",
            params={"page": 1, "size": 50, "keyword": suffix, "task_type": TASK_TYPE},
        )
        assert resp.status_code == 200, resp.text
        assert [it["id"] for it in resp.json()["items"]] == [task_id]

        # 4. 取消: 204, 详情状态变为 cancelled
        resp = await client.post(f"{BASE}/{task_id}/cancel")
        assert resp.status_code == 204, resp.text
        resp = await client.get(f"{BASE}/{task_id}")
        assert resp.json()["status"] == "cancelled", resp.text

        # 5. 已结束任务不可重复取消(400); 从 Celery 同步不覆盖已确认终态(200)
        resp = await client.post(f"{BASE}/{task_id}/cancel")
        assert resp.status_code == 400, resp.text
        resp = await client.post(f"{BASE}/{task_id}/sync")
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "cancelled", resp.text

        # 6. 列表状态过滤(终态稳定, 无竞态): cancelled 可见, pending/success 不可见
        resp = await client.get(
            f"{BASE}/list",
            params={"page": 1, "size": 50, "keyword": suffix, "status": "cancelled"},
        )
        assert resp.status_code == 200, resp.text
        assert [it["id"] for it in resp.json()["items"]] == [task_id]
        for absent_status in ("pending", "success"):
            resp = await client.get(
                f"{BASE}/list",
                params={"page": 1, "size": 50, "keyword": suffix, "status": absent_status},
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["items"] == [], f"cancelled 任务不应出现在 {absent_status} 过滤中"

        # 7. 删除清理: 204 后详情 404, 列表不再可见
        resp = await client.delete(f"{BASE}/{task_id}")
        assert resp.status_code == 204, resp.text
        resp = await client.get(f"{BASE}/{task_id}")
        assert resp.status_code == 404, resp.text
        resp = await client.get(
            f"{BASE}/list", params={"page": 1, "size": 50, "keyword": suffix}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["items"] == []
    finally:
        await _cleanup_task(client, task_id)


async def test_task_delete_pending_directly(client: httpx.AsyncClient):
    """pending 任务可直接删除(任何状态均可删除), 删除后不可再查询"""
    suffix = _suffix()
    task_id = await _create_task(client, _make_task_data(suffix))
    try:
        resp = await client.delete(f"{BASE}/{task_id}")
        assert resp.status_code == 204, resp.text
        resp = await client.get(f"{BASE}/{task_id}")
        assert resp.status_code == 404, resp.text
    finally:
        await _cleanup_task(client, task_id)


async def test_task_retry_after_cancel(client: httpx.AsyncClient):
    """取消后重试: 状态重置为活跃态, 进度/错误/结束时间清空"""
    suffix = _suffix()
    task_id = await _create_task(client, _make_task_data(suffix))
    try:
        resp = await client.post(f"{BASE}/{task_id}/cancel")
        assert resp.status_code == 204, resp.text

        # 重试已结束任务: 重置后重新投递, 立即返回(不等 worker 执行)
        resp = await client.post(f"{BASE}/{task_id}/retry")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] in ("pending", "running"), f"重试后应为活跃态: {body}"
        assert body["error"] is None, f"重试应清空失败原因: {body}"
        assert body["finished_at"] is None, f"重试应清空结束时间: {body}"
        assert body["progress"] == 0, f"重试应重置进度: {body}"
    finally:
        await _cleanup_task(client, task_id)


async def test_task_registry(client: httpx.AsyncClient):
    """任务类型注册表: 应包含 demo_document 且结构完整(供前端下拉/默认模板)"""
    resp = await client.get(f"{BASE}/registry")
    assert resp.status_code == 200, resp.text
    types = resp.json()
    assert isinstance(types, list) and types, f"注册表不应为空: {types}"
    item = next((t for t in types if t.get("type") == TASK_TYPE), None)
    assert item, f"注册表应包含 {TASK_TYPE}: {types}"
    for key in ("name", "description", "celery_task", "default_payload"):
        assert item.get(key), f"注册项缺少字段 {key}: {item}"
    assert item["celery_task"] == "task.run_demo_document"
    assert "file_name" in item["default_payload"], "默认模板应含 file_name"


async def test_task_stats_delta(client: httpx.AsyncClient):
    """统计接口: 结构完整且创建/删除后 total 相对增量正确(不受存量任务影响)"""
    resp = await client.get(f"{BASE}/stats")
    assert resp.status_code == 200, resp.text
    before = resp.json()
    for key in ("total", "pending", "running", "success", "failed", "cancelled"):
        assert isinstance(before.get(key), int), f"统计字段 {key} 应为整数: {before}"

    task_id = await _create_task(client, _make_task_data(_suffix()))
    try:
        resp = await client.get(f"{BASE}/stats")
        after = resp.json()
        assert after["total"] == before["total"] + 1, f"创建后 total 应 +1: {before} -> {after}"
    finally:
        await _cleanup_task(client, task_id)

    resp = await client.get(f"{BASE}/stats")
    final = resp.json()
    assert final["total"] == before["total"], f"删除后 total 应还原: {before} -> {final}"


async def test_task_list_structure(client: httpx.AsyncClient):
    """分页列表结构: items/total/page/size/pages 齐全, 列表项含 Celery 对照字段"""
    resp = await client.get(f"{BASE}/list", params={"page": 1, "size": 5})
    assert resp.status_code == 200, resp.text
    page = resp.json()
    for key in ("items", "total", "page", "size", "pages"):
        assert key in page, f"分页响应缺少字段 {key}: {page}"
    assert isinstance(page["items"], list), "items 应为列表"
    assert len(page["items"]) <= 5, "size=5 时条目数不应超过 5"
    assert page["page"] == 1 and page["size"] == 5
    if page["items"]:
        assert "celery_state" in page["items"][0], "列表项应含 Celery 状态对照字段"


async def test_task_create_invalid_type(client: httpx.AsyncClient):
    """未注册的任务类型应 400, 且不产生任务记录"""
    suffix = _suffix()
    data = _make_task_data(suffix)
    data["task_type"] = f"no_such_type_{suffix}"
    resp = await client.post(BASE, json=data)
    assert resp.status_code == 400, resp.text
    assert "未注册" in resp.json()["detail"], resp.text
    # 创建失败不应留下记录
    resp = await client.get(
        f"{BASE}/list", params={"page": 1, "size": 50, "keyword": suffix}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 0, "未注册类型不应产生任务记录"


async def test_task_create_validation(client: httpx.AsyncClient):
    """创建参数校验: 缺少必填字段/名称超长应 422"""
    suffix = _suffix()
    # 缺少必填字段 name
    resp = await client.post(BASE, json={"task_type": TASK_TYPE})
    assert resp.status_code == 422, resp.text
    # 缺少必填字段 task_type
    resp = await client.post(BASE, json={"name": f"接口测试_{suffix}"})
    assert resp.status_code == 422, resp.text
    # name 超过 200 字符上限
    resp = await client.post(BASE, json={"name": "超" * 201, "task_type": TASK_TYPE})
    assert resp.status_code == 422, resp.text


async def test_task_not_found(client: httpx.AsyncClient):
    """不存在的任务: 详情/删除/同步/取消/重试 均 404(TaskNotFoundError 映射)"""
    ghost = f"nonexistent_{_suffix()}"
    resp = await client.get(f"{BASE}/{ghost}")
    assert resp.status_code == 404, resp.text
    resp = await client.delete(f"{BASE}/{ghost}")
    assert resp.status_code == 404, resp.text
    resp = await client.post(f"{BASE}/{ghost}/sync")
    assert resp.status_code == 404, resp.text
    resp = await client.post(f"{BASE}/{ghost}/cancel")
    assert resp.status_code == 404, resp.text
    resp = await client.post(f"{BASE}/{ghost}/retry")
    assert resp.status_code == 404, resp.text


async def test_task_list_pagination_validation(client: httpx.AsyncClient):
    """分页参数校验: page<1 / size<1 / size>500 → 422

    PaginationParams 的 field_validator 在依赖模型实例化阶段抛出 pydantic
    ValidationError, 已通过全局 exception_handler 统一映射为 422。
    """
    bad_params = (
        {"page": 0, "size": 10},
        {"page": -1, "size": 10},
        {"page": 1, "size": 0},
        {"page": 1, "size": 501},
    )
    for params in bad_params:
        resp = await client.get(f"{BASE}/list", params=params)
        assert resp.status_code == 422, f"{params}: {resp.text}"
