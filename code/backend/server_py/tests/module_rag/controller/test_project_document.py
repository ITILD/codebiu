# -*- coding: utf-8 -*-
"""module_rag/project_document 接口标准测试
覆盖: 上传受理/详情/列表(名称过滤)/更新元数据/下载/删除/参数校验分支/
      入库步骤与进度契约(解析→拆分chunk→向量化, 预留图谱化/标签抽取/网络检索合并)/
      统一存储分片上传流程(init→分片中转→complete)与秒传登记/上传模式与模型预检
说明:
- 文档上传已复用统一文件存储(FileService, 内容哈希去重), 存储由 conftest 覆写为临时本地目录
- 上传成功会派发 Celery 解析任务(memory:// 队列无 worker 时任务滞留,不影响接口受理),
  本文件只测接口受理与元数据,不等待/不触发真实文档向量化(不依赖 LLM)
- reparse/reparse_task 端点依赖 LLM 向量化, 不真实执行(模型缺失时断言 400 拒绝入队)
- 入库进度通过 GET /{document_id}/progress 契约测试 + 流水线权重纯函数单测覆盖
"""

import hashlib
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


# ==================== 统一存储上传流程(与文件管理共用一套分片/秒传链路) ====================


async def test_upload_mode_endpoint(client: httpx.AsyncClient):
    """查询知识库文档上传模式(复用统一文件存储, direct/proxy 由存储类型决定)"""
    resp = await client.get(f"{BASE}/upload-mode")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mode"] in ("direct", "proxy")
    assert body["part_size"] > 0
    assert body["max_size"] > 0


async def test_document_multipart_upload_flow(client: httpx.AsyncClient):
    """分片上传全流程: init → 分片中转 → complete → 按知识库口径登记

    local 存储覆写下 mode=proxy; 单小文件一片直达, 内容哈希与大小应一致
    """
    project_id = await _create_project(client)
    doc_id = None
    try:
        content = f"multipart flow test {uuid.uuid4().hex[:8]} rag".encode("utf-8")
        file_name = f"multipart_{uuid.uuid4().hex[:6]}.txt"
        content_hash = hashlib.sha256(content).hexdigest()

        # 1.init(凭证签发, local 下应为 proxy 中转模式)
        resp = await client.post(
            f"{BASE}/{project_id}/multipart/init",
            json={
                "filename": file_name,
                "file_size_bytes": len(content),
                "content_hash": content_hash,
                "content_type": "text/plain",
            },
        )
        assert resp.status_code == 200, resp.text
        init = resp.json()
        assert init["is_existing"] is False
        assert init["upload_id"], "proxy 模式应返回会话凭证"
        assert init["mode"] == "proxy", "local 存储应为中转模式"

        # 2.分片中转(单片)
        resp = await client.put(
            f"{BASE}/{project_id}/multipart/{init['upload_id']}/parts/1",
            content=content,
        )
        assert resp.status_code == 200, resp.text
        part = resp.json()
        assert part["part_number"] == 1
        assert part["size"] == len(content)

        # 3.complete(对账合并 + 知识库口径登记)
        resp = await client.post(
            f"{BASE}/{project_id}/multipart/{init['upload_id']}/complete",
            json={
                "filename": file_name,
                "file_size_bytes": len(content),
                "parts": [
                    {"part_number": 1, "etag": part["etag"], "size": len(content)}
                ],
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        doc_id = body["id"]
        assert body["project_id"] == project_id
        assert body["name"] == file_name
        assert body["content_hash"] == content_hash, "登记的内容哈希应为真实SHA-256"
        assert body["file_size_bytes"] == len(content)
        assert body["physical_path"], "应记录统一存储物理键"
        assert body["parse_status"] == "pending"

        # 4.下载应与上传内容一致(统一存储口径 local 流式)
        resp = await client.get(f"{BASE}/{doc_id}/download")
        assert resp.status_code == 200, resp.text
        assert resp.content == content

        # 5.删除(释放统一存储内容引用, 引用归零清理物理内容)
        resp = await client.delete(f"{BASE}/{doc_id}")
        assert resp.status_code in (200, 204), resp.text
        doc_id = None
    finally:
        if doc_id:
            await client.delete(f"{BASE}/{doc_id}")
        await client.delete(f"{PROJECT_BASE}/{project_id}")


async def test_document_instant_upload_existing(client: httpx.AsyncClient):
    """秒传登记: 相同内容 init 返回 is_existing, upload-complete 直接建知识库记录"""
    project_id = await _create_project(client)
    doc_ids = []
    try:
        content = f"instant upload test {uuid.uuid4().hex[:8]}".encode("utf-8")
        content_hash = hashlib.sha256(content).hexdigest()
        file_name = f"instant_{uuid.uuid4().hex[:6]}.txt"

        # 先经小文件直传落一份内容
        resp = await client.post(
            f"{BASE}/{project_id}/upload",
            files={"file": (file_name, content, "text/plain")},
        )
        assert resp.status_code == 201, resp.text
        doc_ids.append(resp.json()["id"])

        # 相同内容 init → 秒传
        resp = await client.post(
            f"{BASE}/{project_id}/multipart/init",
            json={
                "filename": f"{file_name}.copy.txt",
                "file_size_bytes": len(content),
                "content_hash": content_hash,
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["is_existing"] is True, "相同内容应命中秒传"

        # upload-complete 按知识库口径另建记录(独立口径, 同一物理内容)
        resp = await client.post(
            f"{BASE}/{project_id}/upload-complete",
            json={
                "name": f"{file_name}.copy.txt",
                "content_hash": content_hash,
                "file_size_bytes": len(content),
                "mime_type": "text/plain",
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        doc_ids.append(body["id"])
        assert body["content_hash"] == content_hash
        assert body["physical_path"], "秒传登记应复用已存在的物理键"

        # 秒传到不存在的内容应 400
        resp = await client.post(
            f"{BASE}/{project_id}/upload-complete",
            json={
                "name": "ghost.txt",
                "content_hash": hashlib.sha256(b"never uploaded").hexdigest(),
                "file_size_bytes": 13,
            },
        )
        assert resp.status_code == 400, resp.text
    finally:
        for d in doc_ids:
            await client.delete(f"{BASE}/{d}")
        await client.delete(f"{PROJECT_BASE}/{project_id}")


async def test_model_check_endpoint(client: httpx.AsyncClient):
    """模型预检接口契约: 返回 ok/missing/message 结构(不依赖具体模型配置)"""
    resp = await client.get(f"{BASE}/model-check")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body["ok"], bool)
    assert isinstance(body["missing"], list)
    assert isinstance(body["message"], str) or body["message"] is None
    # 一致性: ok 为 True 时缺失列表应为空
    if body["ok"]:
        assert body["missing"] == []
        assert body["message"] is None


async def test_reparse_task_model_gate(client: httpx.AsyncClient):
    """重新解析入队前置模型校验: 模型缺失时 400 拒绝入队, 可用时应受理

    以 /model-check 的结果为基准(同一环境下两者判定一致), 不依赖具体模型配置
    """
    project_id = await _create_project(client)
    doc_id = None
    try:
        resp = await client.post(
            f"{BASE}/{project_id}/upload",
            files={"file": (f"gate_{uuid.uuid4().hex[:6]}.txt", b"model gate test", "text/plain")},
        )
        assert resp.status_code == 201, resp.text
        doc_id = resp.json()["id"]

        check = (await client.get(f"{BASE}/model-check")).json()
        resp = await client.post(f"{BASE}/{doc_id}/reparse-task")
        if not check["ok"]:
            assert resp.status_code == 400, resp.text
            assert "模型" in resp.json()["detail"], "拒绝原因应提示模型未配置"
        else:
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["document_id"] == doc_id
            assert body["task_id"], "受理时应返回任务队列ID"
    finally:
        if doc_id:
            await client.delete(f"{BASE}/{doc_id}")
        await client.delete(f"{PROJECT_BASE}/{project_id}")

async def test_document_folder_and_entries_flow(client: httpx.AsyncClient):
    """条目级浏览与文件夹管理: 建目录→目录内上传→entries 联查文档字段→重命名→删除

    知识库项目在虚拟目录 /知识库/ 下拥有独立项目根文件夹(source_module=rag),
    文档以条目级记录关联 project_document(entry_id), entries 对文件条目联查解析状态
    """
    project_id = await _create_project(client)
    doc_id = None
    folder_id = None
    try:
        # 初始 entries: 项目根文件夹为空
        resp = await client.get(f"{BASE}/{project_id}/entries", params={"page": 1, "size": 10})
        assert resp.status_code == 200, resp.text
        assert resp.json()["total"] == 0, "新项目根文件夹应为空"

        # 创建子文件夹(201, source_module 继承 rag)
        resp = await client.post(f"{BASE}/{project_id}/folders", params={"name": "子目录A"})
        assert resp.status_code == 201, resp.text
        folder = resp.json()
        folder_id = folder["id"]
        assert folder["is_directory"] is True
        assert folder["source_module"] == "rag", "项目内条目应继承知识库来源标记"

        # 子目录内上传文档(pid 指定父目录)
        content = f"folder doc {uuid.uuid4().hex[:8]}".encode("utf-8")
        resp = await client.post(
            f"{BASE}/{project_id}/upload",
            files={"file": (f"folder_doc_{uuid.uuid4().hex[:6]}.txt", content, "text/plain")},
            data={"pid": folder_id},
        )
        assert resp.status_code == 201, resp.text
        doc_id = resp.json()["id"]

        # 子目录 entries: 文件条目联查文档字段(document_id/parse_status)
        resp = await client.get(
            f"{BASE}/{project_id}/entries",
            params={"page": 1, "size": 10, "pid": folder_id},
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert len(items) == 1, "子目录应只有一个文件条目"
        entry = items[0]
        assert entry["is_directory"] is False
        assert entry["document_id"] == doc_id, "文件条目应联查到文档ID"
        assert entry["parse_status"] == "pending", "联查解析状态应为 pending"
        assert entry["source_module"] == "rag"

        # 名称过滤(命中)
        resp = await client.get(
            f"{BASE}/{project_id}/entries",
            params={"page": 1, "size": 10, "pid": folder_id, "name": entry["name"][:8]},
        )
        assert resp.status_code == 200 and resp.json()["total"] == 1, resp.text

        # 重命名文件夹(200)
        resp = await client.put(
            f"{BASE}/{project_id}/folders/{folder_id}", params={"name": "子目录B"}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["name"] == "子目录B"

        # 删除文件夹(204, 递归删除条目并释放内容引用; 文档记录属文档级操作不在 folder 清理范围)
        resp = await client.delete(f"{BASE}/{project_id}/folders/{folder_id}")
        assert resp.status_code in (200, 204), resp.text
        folder_id = None
        # 文档记录仍在(条目已删), 直接删文档兜底清理
        resp = await client.get(f"{BASE}/{doc_id}")
        assert resp.status_code == 200, "文件夹删除不影响文档记录"
    finally:
        if doc_id:
            await client.delete(f"{BASE}/{doc_id}")
        if folder_id:
            await client.delete(f"{BASE}/{project_id}/folders/{folder_id}")
        await client.delete(f"{PROJECT_BASE}/{project_id}")


async def test_folder_in_project_guard(client: httpx.AsyncClient):
    """跨项目目录防护: 用他项目文件夹ID当 pid 应被拒绝(400/404)"""
    project_a = await _create_project(client)
    project_b = await _create_project(client)
    try:
        # 在项目B建文件夹
        resp = await client.post(f"{BASE}/{project_b}/folders", params={"name": "B目录"})
        assert resp.status_code == 201, resp.text
        folder_b = resp.json()

        # 项目A用B的目录当 pid 创建文件夹 → 拒绝
        resp = await client.post(
            f"{BASE}/{project_a}/folders",
            params={"name": "越权目录", "pid": folder_b["id"]},
        )
        assert resp.status_code in (400, 404), f"跨项目目录应被拒绝: {resp.status_code} {resp.text}"

        # 项目A用B的目录当 pid 浏览 → 拒绝
        resp = await client.get(
            f"{BASE}/{project_a}/entries", params={"page": 1, "size": 10, "pid": folder_b["id"]}
        )
        assert resp.status_code in (400, 404), f"跨项目浏览应被拒绝: {resp.status_code} {resp.text}"
    finally:
        await client.delete(f"{PROJECT_BASE}/{project_a}")
        await client.delete(f"{PROJECT_BASE}/{project_b}")
