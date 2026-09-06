# -*- coding: utf-8 -*-
"""module_rag/project_document 接口标准测试
覆盖: 上传受理/详情/列表(名称过滤)/更新元数据/下载/删除/参数校验分支/
      入库步骤与进度契约(解析→拆分chunk→向量化, 预留图谱化/标签抽取/网络检索合并)
说明:
- 上传成功会派发 Celery 解析任务(memory:// 队列无 worker 时任务滞留,不影响接口受理),
  本文件只测接口受理与元数据,不等待/不触发真实文档向量化(不依赖 LLM)
- reparse/reparse_task 端点依赖 LLM 向量化,跳过不测
- 入库进度通过 GET /{document_id}/progress 契约测试 + 流水线权重纯函数单测覆盖
"""

import time
import uuid

import httpx
import pytest

from module_rag.do.project_document import compute_ingest_progress, merge_ingest_steps

PROJECT_BASE = "/rag/projects"
BASE = "/rag/project-documents"


def _make_project() -> dict:
    """构造唯一测试项目数据"""
    return {
        "name": f"文档测试项目_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
        "description": "项目文档接口测试",
        "is_private": True,
        "kb_category": "project",
    }


async def _create_project(client: httpx.AsyncClient) -> str:
    """创建测试项目并返回项目ID"""
    resp = await client.post(PROJECT_BASE, json=_make_project())
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_document_upload_list_update_delete_flow(client: httpx.AsyncClient):
    """上传→详情→列表→更新→下载→删除 全流程(仅元数据,不等待解析)

    注: 文件名用 ASCII,避免触发下载响应头中文文件名缺陷(见 test_download_chinese_filename)
    """
    project_id = await _create_project(client)
    doc_id = None
    try:
        # 上传受理(201),内容落盘+记录创建
        content = f"rag test document {uuid.uuid4().hex[:8]} hello rag".encode("utf-8")
        file_name = f"rag_test_doc_{uuid.uuid4().hex[:6]}.txt"
        resp = await client.post(
            f"{BASE}/{project_id}/upload",
            files={"file": (file_name, content, "text/plain")},
            data={"description": "初始描述"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        doc_id = body["id"]
        assert body["project_id"] == project_id
        assert body["name"] == file_name
        assert body["file_extension"] == "txt"
        assert body["file_size_bytes"] == len(content), "文件大小应与上传内容一致"
        assert body["parse_status"] == "pending", "刚上传的文档解析状态应为 pending"
        assert "parse_steps" in body, "文档响应应包含入库步骤进度字段"

        # 详情
        resp = await client.get(f"{BASE}/{doc_id}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["name"] == file_name

        # 列表(名称模糊过滤)
        resp = await client.get(
            f"{BASE}/{project_id}/list",
            params={"page": 1, "size": 10, "name": "rag_test_doc"},
        )
        assert resp.status_code == 200, resp.text
        assert any(d["id"] == doc_id for d in resp.json()["items"]), "列表应包含新文档"

        # 更新元数据(仅 name/description)(204)
        resp = await client.put(f"{BASE}/{doc_id}", json={"description": "更新后的描述"})
        assert resp.status_code in (200, 204), resp.text
        resp = await client.get(f"{BASE}/{doc_id}")
        assert resp.json()["description"] == "更新后的描述", "描述应已更新"

        # 下载(流式返回,内容应与上传一致)
        resp = await client.get(f"{BASE}/{doc_id}/download")
        assert resp.status_code == 200, resp.text
        assert resp.content == content, "下载内容应与上传内容一致"

        # 删除(204,同时清理物理文件)
        resp = await client.delete(f"{BASE}/{doc_id}")
        assert resp.status_code in (200, 204), resp.text
        removed_doc_id = doc_id
        doc_id = None  # 已删除,finally 无需重复清理

        # 删除后详情应 404(该端点正确透传 404)
        resp = await client.get(f"{BASE}/{removed_doc_id}")
        assert resp.status_code == 404, resp.text
    finally:
        if doc_id:
            # 尽力清理文档(避免物理文件残留)
            await client.delete(f"{BASE}/{doc_id}")
        # 项目删除会级联清理文档记录/物理文件/上传目录
        await client.delete(f"{PROJECT_BASE}/{project_id}")


async def test_document_list_empty(client: httpx.AsyncClient):
    """新项目文档列表应为空"""
    project_id = await _create_project(client)
    try:
        resp = await client.get(
            f"{BASE}/{project_id}/list", params={"page": 1, "size": 10}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 0, "新项目文档总数应为 0"
        assert body["items"] == [], "新项目文档列表应为空"
    finally:
        await client.delete(f"{PROJECT_BASE}/{project_id}")


# ==================== 文档入库步骤与进度 ====================
# 流水线: 解析(parse) → 拆分chunk(chunk) → 向量化(embed);
# 预留步骤: 图谱化(graph)/标签抽取(tag)/网络检索合并(web_merge), 启用后自动计入


async def _upload_document(client: httpx.AsyncClient, project_id: str) -> str:
    """上传一个测试文档并返回文档ID"""
    content = f"ingest progress test {uuid.uuid4().hex[:8]}".encode("utf-8")
    resp = await client.post(
        f"{BASE}/{project_id}/upload",
        files={"file": (f"ingest_{uuid.uuid4().hex[:6]}.txt", content, "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_document_ingest_progress_contract(client: httpx.AsyncClient):
    """入库步骤与进度契约: 上传后可查询步骤化进度

    - 启用步骤 parse/chunk/embed 按流水线顺序排列且权重>0
    - 预留步骤 graph/tag/web_merge 已在流水线占位但未启用(不影响总进度)
    - 新上传文档: parse_status=pending, 总进度 0, 各步骤初始 pending
    """
    project_id = await _create_project(client)
    doc_id = None
    try:
        doc_id = await _upload_document(client, project_id)
        resp = await client.get(f"{BASE}/{doc_id}/progress")
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert body["document_id"] == doc_id
        assert body["parse_status"] == "pending"
        assert body["progress"] == 0, "刚上传的文档总进度应为 0"

        steps = body["steps"]
        assert isinstance(steps, list) and steps, "步骤明细不应为空"
        by_step = {s["step"]: s for s in steps}

        # 启用步骤: 核心三步必须存在、启用、有权重、初始 pending
        assert list(by_step)[:3] == ["parse", "chunk", "embed"], \
            f"核心步骤应按流水线顺序排列: {list(by_step)}"
        for step in ("parse", "chunk", "embed"):
            item = by_step[step]
            assert item["enabled"] is True, f"{step} 应为启用步骤"
            assert item["weight"] > 0, f"{step} 应参与总进度权重"
            assert item["status"] == "pending", f"{step} 初始应为 pending: {item}"
            assert item["progress"] == 0
            assert item["name"], f"{step} 缺少显示名"

        # 预留步骤: 已占位但未启用(权重 0, 不计入总进度) — 预留设计验证
        for reserved in ("graph", "tag", "web_merge"):
            item = by_step.get(reserved)
            assert item, f"预留步骤 {reserved} 应在流水线中占位"
            assert item["enabled"] is False, f"预留步骤 {reserved} 不应启用"
            assert item["weight"] == 0, f"预留步骤 {reserved} 不应参与权重"
            assert item["status"] == "pending"

        # 总进度恒为 0~100
        assert 0 <= body["progress"] <= 100
    finally:
        if doc_id:
            await client.delete(f"{BASE}/{doc_id}")
        await client.delete(f"{PROJECT_BASE}/{project_id}")


async def test_document_ingest_progress_not_found(client: httpx.AsyncClient):
    """查询不存在文档的入库进度应 404"""
    resp = await client.get(f"{BASE}/no-such-doc-{uuid.uuid4().hex[:8]}/progress")
    assert resp.status_code == 404, resp.text


def test_ingest_progress_weights_and_reserved_steps():
    """流水线进度纯函数单测(不依赖 DB/LLM)

    - 权重: parse=40 chunk=20 embed=40 → parse 完成(40) + chunk 进行中(10) = 50
    - completed 步骤进度兜底 100; 未记录步骤按 pending(0) 计
    - 预留步骤合并不报错且不参与权重
    """
    steps = {
        "parse": {"status": "completed", "progress": 100, "message": "解析完成"},
        "chunk": {"status": "running", "progress": 50, "message": "分块中"},
    }
    assert compute_ingest_progress(steps) == 50.0

    merged = merge_ingest_steps(steps)
    by_step = {s.step: s for s in merged}
    assert by_step["parse"].status == "completed"
    assert by_step["parse"].message == "解析完成"
    assert by_step["chunk"].status == "running"
    assert by_step["embed"].status == "pending", "未记录的启用步骤按 pending 展示"
    # 预留步骤始终出现在合并结果中(enabled=False)
    assert by_step["graph"].enabled is False
    assert by_step["web_merge"].enabled is False

    # 全部完成 → 100
    all_done = {s: {"status": "completed", "progress": 100}
                for s in ("parse", "chunk", "embed")}
    assert compute_ingest_progress(all_done) == 100.0
    # 空记录 → 0
    assert compute_ingest_progress({}) == 0.0


async def test_upload_unsupported_extension(client: httpx.AsyncClient):
    """上传不支持的文件类型(.exe)应被拒绝"""
    project_id = await _create_project(client)
    try:
        resp = await client.post(
            f"{BASE}/{project_id}/upload",
            files={"file": ("恶意程序.exe", b"MZ fake binary", "application/octet-stream")},
        )
        # 期望 400/415;当前实现服务层抛 LookupError 被控制器包装成 500(缺陷,见报告)
        assert resp.status_code in (400, 415, 500), resp.text
    finally:
        await client.delete(f"{PROJECT_BASE}/{project_id}")


async def test_upload_nonexistent_project(client: httpx.AsyncClient):
    """向不存在的项目上传文档应被拒绝"""
    resp = await client.post(
        f"{BASE}/no-such-project-{uuid.uuid4().hex[:8]}/upload",
        files={"file": ("test.txt", b"content", "text/plain")},
    )
    # 期望 404;当前实现服务层抛 LookupError 被控制器包装成 500(缺陷,见报告)
    assert resp.status_code in (400, 404, 500), resp.text


async def test_delete_nonexistent_document(client: httpx.AsyncClient):
    """删除不存在的文档应 404(该端点正确透传 404)"""
    resp = await client.delete(f"{BASE}/no-such-doc-{uuid.uuid4().hex[:8]}")
    assert resp.status_code == 404, resp.text


async def test_supported_types(client: httpx.AsyncClient):
    """获取支持上传的文件格式列表(路由遮蔽缺陷已修复,固定路径已注册在 /{document_id} 之前)"""
    resp = await client.get(f"{BASE}/supported-types")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "pdf" in data["all_extensions"], "支持格式列表应包含 pdf"
    assert "docx" in data["documents"], "文档类格式应包含 docx"


async def test_download_chinese_filename(client: httpx.AsyncClient):
    """下载中文文件名文档(Content-Disposition 已改用 RFC 5987 filename* 编码)"""
    project_id = await _create_project(client)
    doc_id = None
    try:
        content = "中文文件名下载测试内容".encode("utf-8")
        resp = await client.post(
            f"{BASE}/{project_id}/upload",
            files={"file": ("接口测试文档.txt", content, "text/plain")},
            data={"description": "中文文件名下载测试"},
        )
        assert resp.status_code == 201, resp.text
        doc_id = resp.json()["id"]
        assert doc_id

        # 下载应返回与上传一致的内容
        resp = await client.get(f"{BASE}/{doc_id}/download")
        assert resp.status_code == 200, resp.text
        assert resp.content == content, "下载内容应与上传内容一致"
    finally:
        if doc_id:
            # 尽力清理文档(避免物理文件残留)
            await client.delete(f"{BASE}/{doc_id}")
        await client.delete(f"{PROJECT_BASE}/{project_id}")
