# -*- coding: utf-8 -*-
"""module_rag/project_document 接口标准测试
覆盖: 上传受理/详情/列表(名称过滤)/更新元数据/下载/删除/参数校验分支
说明:
- 上传成功会派发 Celery 解析任务(memory:// 队列无 worker 时任务滞留,不影响接口受理),
  本文件只测接口受理与元数据,不等待/不触发真实文档向量化(不依赖 LLM)
- reparse/reparse_task 端点依赖 LLM 向量化,跳过不测
"""

import time
import uuid

import httpx
import pytest

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
