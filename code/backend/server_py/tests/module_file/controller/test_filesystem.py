"""module_file controller 接口测试
覆盖: 小文件直传/下载/列表/删除、同名冲突、分片上传全流程、秒传去重、取消分片、非法凭证
存储由 tests/module_file/conftest.py 强制替换为临时本地目录,零外部依赖。
"""

import hashlib
import logging
import os

import pytest

logger = logging.getLogger(__name__)

BASE = "/file/filesystem"

UPLOAD_URL = f"{BASE}/upload"
MULTIPART_INIT_URL = f"{BASE}/multipart/init"
MULTIPART_PART_URL = f"{BASE}/multipart/{{upload_id}}/parts/{{part_number}}"
MULTIPART_COMPLETE_URL = f"{BASE}/multipart/{{upload_id}}/complete"
MULTIPART_ABORT_URL = f"{BASE}/multipart/{{upload_id}}"
UPLOAD_COMPLETE_URL = f"{BASE}/upload-complete"
LIST_DIR_URL = f"{BASE}/list-dir"
DOWNLOAD_URL = f"{BASE}/download/{{entry_id}}"
ENTRY_URL = f"{BASE}/entries/{{entry_id}}"
DELETE_FILE_URL = f"{BASE}/files/{{file_id}}"

# 标准分片大小(与 service 常量一致)
PART_SIZE = 8 * 1024 * 1024


# ==================== 直传 ====================
@pytest.mark.asyncio
async def test_upload_download_list_delete(client):
    """直传 -> 列表 -> 元数据 -> 下载 -> 删除 全流程"""
    filename = f"direct_{os.urandom(4).hex()}.txt"
    content = f"hello filesystem {os.urandom(8).hex()}".encode()
    content_hash = hashlib.sha256(content).hexdigest()

    # 1. 上传
    resp = await client.post(
        UPLOAD_URL,
        files={"file": (filename, content, "text/plain")},
    )
    assert resp.status_code == 201, f"直传失败: {resp.text}"
    entry = resp.json()
    assert entry["name"] == filename
    assert entry["content_hash"] == content_hash
    assert entry["file_size_bytes"] == len(content)
    assert entry["is_directory"] is False
    entry_id = entry["id"]

    # 2. 列表可见
    resp = await client.get(LIST_DIR_URL, params={"page": 1, "size": 50})
    assert resp.status_code == 200
    names = [it["name"] for it in resp.json()["items"]]
    assert filename in names

    # 3. 元数据
    resp = await client.get(ENTRY_URL.format(entry_id=entry_id))
    assert resp.status_code == 200
    assert resp.json()["logical_path"] == f"/{filename}"

    # 4. 下载内容一致
    resp = await client.get(DOWNLOAD_URL.format(entry_id=entry_id))
    assert resp.status_code == 200
    assert resp.content == content

    # 5. 删除
    resp = await client.delete(DELETE_FILE_URL.format(file_id=entry_id))
    assert resp.status_code == 204
    resp = await client.get(ENTRY_URL.format(entry_id=entry_id))
    assert resp.status_code == 200  # 逻辑删除后元数据仍可查
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_upload_duplicate_name_conflict(client):
    """同目录同名文件冲突返回 409(ConflictError)"""
    filename = f"dup_{os.urandom(4).hex()}.txt"
    for _ in range(2):
        resp = await client.post(
            UPLOAD_URL,
            files={"file": (filename, os.urandom(16), "text/plain")},
        )
    assert resp.status_code == 409
    assert "同名" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_dedupe_same_content(client):
    """相同内容不同文件名: 内容哈希去重,引用同一物理记录"""
    content = b"dedupe content " + os.urandom(8)
    content_hash = hashlib.sha256(content).hexdigest()
    ids = []
    for name in (
        f"same_a_{os.urandom(4).hex()}.txt",
        f"same_b_{os.urandom(4).hex()}.txt",
    ):
        resp = await client.post(
            UPLOAD_URL, files={"file": (name, content, "text/plain")}
        )
        assert resp.status_code == 201, resp.text
        ids.append(resp.json())
    assert ids[0]["content_hash"] == ids[1]["content_hash"] == content_hash

    for e in ids:
        await client.delete(DELETE_FILE_URL.format(file_id=e["id"]))


# ==================== 分片上传 ====================
def _make_part_data(total_bytes: int) -> bytes:
    """生成分片测试数据"""
    return os.urandom(total_bytes)


@pytest.mark.asyncio
async def test_multipart_upload_flow(client):
    """分片上传全流程: init -> 3片上传 -> complete -> 下载校验 -> 删除"""
    filename = f"mp_{os.urandom(4).hex()}.bin"
    # 8MB + 8MB + 4MB = 20MB, 最后一片小于标准分片
    content = _make_part_data(PART_SIZE * 2 + PART_SIZE // 2)
    content_hash = hashlib.sha256(content).hexdigest()

    # 1. 初始化
    resp = await client.post(
        MULTIPART_INIT_URL,
        json={
            "filename": filename,
            "file_size_bytes": len(content),
            "content_hash": content_hash,
            "content_type": "application/octet-stream",
        },
    )
    assert resp.status_code == 200, f"init 失败: {resp.text}"
    init = resp.json()
    assert init["is_existing"] is False
    assert init["upload_id"]
    assert init["part_size"] == PART_SIZE
    upload_id = init["upload_id"]

    # 2. 逐片上传
    parts = []
    for i in range(0, len(content), PART_SIZE):
        chunk = content[i : i + PART_SIZE]
        resp = await client.put(
            MULTIPART_PART_URL.format(upload_id=upload_id, part_number=len(parts) + 1),
            content=chunk,
            headers={"Content-Type": "application/octet-stream"},
        )
        assert resp.status_code == 200, f"分片 {len(parts) + 1} 上传失败: {resp.text}"
        part = resp.json()
        assert part["part_number"] == len(parts) + 1
        assert part["size"] == len(chunk)
        parts.append(part)

    # 3. 查询已传分片(断点续传)
    resp = await client.get(f"{BASE}/multipart/{upload_id}/parts")
    assert resp.status_code == 200
    assert len(resp.json()) == len(parts)

    # 4. 完成
    resp = await client.post(
        MULTIPART_COMPLETE_URL.format(upload_id=upload_id),
        json={
            "filename": filename,
            "file_size_bytes": len(content),
            "parts": parts,
        },
    )
    assert resp.status_code == 201, f"complete 失败: {resp.text}"
    entry = resp.json()
    assert entry["name"] == filename
    # 服务端按真实内容计算哈希并归位
    assert entry["content_hash"] == content_hash
    assert entry["file_size_bytes"] == len(content)
    entry_id = entry["id"]

    # 5. 下载内容一致
    resp = await client.get(DOWNLOAD_URL.format(entry_id=entry_id))
    assert resp.status_code == 200
    assert resp.content == content

    # 清理
    resp = await client.delete(DELETE_FILE_URL.format(file_id=entry_id))
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_multipart_dedupe(client):
    """分片上传秒传: 直传过的内容再走分片 init 直接返回已存在"""
    content = b"multipart dedupe " + os.urandom(8)
    content_hash = hashlib.sha256(content).hexdigest()

    # 先直传建立内容
    resp = await client.post(
        UPLOAD_URL,
        files={"file": (f"dedupe_{os.urandom(4).hex()}.txt", content, "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    first = resp.json()

    # 分片 init 命中已完成内容 -> 秒传
    resp = await client.post(
        MULTIPART_INIT_URL,
        json={
            "filename": f"dedupe2_{os.urandom(4).hex()}.txt",
            "file_size_bytes": len(content),
            "content_hash": content_hash,
        },
    )
    assert resp.status_code == 200
    init = resp.json()
    assert init["is_existing"] is True
    assert init["upload_id"] is None

    # 秒传建条目
    resp = await client.post(
        UPLOAD_COMPLETE_URL,
        json={
            "name": f"dedupe2_{os.urandom(4).hex()}.txt",
            "content_hash": content_hash,
            "file_size_bytes": len(content),
            "mime_type": "text/plain",
        },
    )
    assert resp.status_code == 201, resp.text
    second = resp.json()
    assert second["content_hash"] == content_hash
    assert second["id"] != first["id"]

    # 清理
    for e in (first, second):
        await client.delete(DELETE_FILE_URL.format(file_id=e["id"]))


@pytest.mark.asyncio
async def test_multipart_abort(client):
    """取消分片上传: 清理会话,再次查询返回空列表"""
    content = _make_part_data(PART_SIZE)
    resp = await client.post(
        MULTIPART_INIT_URL,
        json={
            "filename": f"abort_{os.urandom(4).hex()}.bin",
            "file_size_bytes": len(content),
            "content_hash": hashlib.sha256(content).hexdigest(),
        },
    )
    upload_id = resp.json()["upload_id"]
    resp = await client.put(
        MULTIPART_PART_URL.format(upload_id=upload_id, part_number=1),
        content=content,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert resp.status_code == 200

    # 取消
    resp = await client.delete(MULTIPART_ABORT_URL.format(upload_id=upload_id))
    assert resp.status_code == 204

    # 已传分片被清理
    resp = await client.get(f"{BASE}/multipart/{upload_id}/parts")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_multipart_invalid_token(client):
    """伪造/篡改的会话凭证被拒绝(400)"""
    resp = await client.put(
        MULTIPART_PART_URL.format(upload_id="fake.notavalidsig", part_number=1),
        content=b"x",
        headers={"Content-Type": "application/octet-stream"},
    )
    assert resp.status_code == 400
    assert "非法" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_multipart_part_too_large(client):
    """单片超过标准分片大小返回 400"""
    content = _make_part_data(PART_SIZE + 1024)
    resp = await client.post(
        MULTIPART_INIT_URL,
        json={
            "filename": f"big_{os.urandom(4).hex()}.bin",
            "file_size_bytes": len(content),
            "content_hash": hashlib.sha256(content).hexdigest(),
        },
    )
    upload_id = resp.json()["upload_id"]
    resp = await client.put(
        MULTIPART_PART_URL.format(upload_id=upload_id, part_number=1),
        content=content,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert resp.status_code == 400
    await client.delete(MULTIPART_ABORT_URL.format(upload_id=upload_id))


# ==================== init 凭证签发阶段校验 ====================
@pytest.mark.asyncio
async def test_multipart_init_duplicate_name(client):
    """init 阶段即校验同名冲突(不签发凭证,数据面未开始)"""
    filename = f"initdup_{os.urandom(4).hex()}.txt"
    content = b"init dup content"
    resp = await client.post(
        UPLOAD_URL,
        files={"file": (filename, content, "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    entry = resp.json()

    # 同目录同名文件再 init -> 409,凭证未签发
    resp = await client.post(
        MULTIPART_INIT_URL,
        json={
            "filename": filename,
            "file_size_bytes": len(content) + PART_SIZE,
            "content_hash": hashlib.sha256(os.urandom(16)).hexdigest(),
        },
    )
    assert resp.status_code == 409
    assert "同名" in resp.json()["detail"]
    await client.delete(DELETE_FILE_URL.format(file_id=entry["id"]))


@pytest.mark.asyncio
async def test_multipart_init_mime_not_allowed(client):
    """init 阶段即校验 MIME 白名单(配置仅允许 image/* 时拒绝文本文件)"""
    import module_file.service.filesystem as fs_service

    original = fs_service.storage_config.allowed_extensions
    fs_service.storage_config.allowed_extensions = ["image/*"]
    try:
        resp = await client.post(
            MULTIPART_INIT_URL,
            json={
                "filename": f"mime_{os.urandom(4).hex()}.txt",
                "file_size_bytes": PART_SIZE,
                "content_hash": hashlib.sha256(os.urandom(16)).hexdigest(),
            },
        )
        assert resp.status_code == 400
        assert "不支持的文件类型" in resp.json()["detail"]
    finally:
        fs_service.storage_config.allowed_extensions = original


@pytest.mark.asyncio
async def test_multipart_init_invalid_pid(client):
    """init 阶段即校验父目录: 不存在的 pid / pid 指向文件 均拒绝"""
    base = {
        "filename": f"pid_{os.urandom(4).hex()}.txt",
        "file_size_bytes": PART_SIZE,
        "content_hash": hashlib.sha256(os.urandom(16)).hexdigest(),
    }
    # pid 不存在(资源不存在语义 -> 404)
    resp = await client.post(MULTIPART_INIT_URL, json={**base, "pid": "no-such-pid"})
    assert resp.status_code == 404
    assert "父目录" in resp.json()["detail"]

    # pid 指向文件(非目录)
    resp = await client.post(
        UPLOAD_URL,
        files={"file": (f"pidfile_{os.urandom(4).hex()}.txt", b"x", "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    file_entry = resp.json()
    resp = await client.post(MULTIPART_INIT_URL, json={**base, "pid": file_entry["id"]})
    assert resp.status_code == 400
    assert "不是目录" in resp.json()["detail"]
    await client.delete(DELETE_FILE_URL.format(file_id=file_entry["id"]))


@pytest.mark.asyncio
async def test_upload_mode_proxy_for_local(client):
    """local 存储(默认测试环境)下 upload-mode 返回 proxy 中转模式"""
    resp = await client.get(f"{BASE}/upload-mode")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "proxy"
    assert data["part_size"] == PART_SIZE
    assert data["max_size"] > 0


@pytest.mark.asyncio
async def test_multipart_proxy_hash_correction(client):
    """中转模式哈希校正: 前端谎报 SHA-256,complete 后条目与内容记录以存储侧真实哈希为准"""
    content = _make_part_data(PART_SIZE)  # 单片恰好等于标准分片大小
    real_hash = hashlib.sha256(content).hexdigest()
    fake_hash = "f" * 64  # 前端谎报的哈希(与真实内容不符)

    resp = await client.post(
        MULTIPART_INIT_URL,
        json={
            "filename": f"hashfix_{os.urandom(4).hex()}.bin",
            "file_size_bytes": len(content),
            "content_hash": fake_hash,
            "content_type": "application/octet-stream",
        },
    )
    assert resp.status_code == 200, resp.text
    upload_id = resp.json()["upload_id"]

    resp = await client.put(
        MULTIPART_PART_URL.format(upload_id=upload_id, part_number=1),
        content=content,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert resp.status_code == 200, resp.text

    resp = await client.post(
        MULTIPART_COMPLETE_URL.format(upload_id=upload_id),
        json={
            "filename": f"hashfix_{os.urandom(4).hex()}.bin",
            "file_size_bytes": len(content),
            "parts": [{"part_number": 1, "size": len(content)}],
        },
    )
    assert resp.status_code == 201, resp.text
    entry = resp.json()
    # 条目哈希被校正为真实 SHA-256
    assert entry["content_hash"] == real_hash
    assert entry["file_size_bytes"] == len(content)

    # 校正后哈希可正常秒传命中(内容记录已归位)
    resp = await client.post(
        MULTIPART_INIT_URL,
        json={
            "filename": f"hashfix2_{os.urandom(4).hex()}.bin",
            "file_size_bytes": len(content),
            "content_hash": real_hash,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["is_existing"] is True

    await client.delete(DELETE_FILE_URL.format(file_id=entry["id"]))

# ==================== 批量删除/条目详情/标签 ====================
BATCH_DELETE_URL = f"{BASE}/entries/batch-delete"
ENTRY_DETAIL_URL = f"{BASE}/entries/{{entry_id}}/detail"
FOLDER_URL = f"{BASE}/folder"
UPDATE_ENTRY_URL = f"{BASE}/entries/{{entry_id}}"
FOLDER_DELETE_URL = f"{BASE}/folders/{{folder_id}}"


@pytest.mark.asyncio
async def test_batch_delete_mixed_entries(client):
    """批量删除: 文件+目录混选,目录递归删除子树,返回成功数"""
    suffix = os.urandom(4).hex()
    # 上传 2 个文件
    file_ids = []
    for name in (f"batch_a_{suffix}.txt", f"batch_b_{suffix}.txt"):
        resp = await client.post(
            UPLOAD_URL, files={"file": (name, b"batch content", "text/plain")}
        )
        assert resp.status_code == 201, resp.text
        file_ids.append(resp.json()["id"])
    # 创建目录并在其中上传 1 个文件
    folder_name = f"batch_dir_{suffix}"
    resp = await client.post(FOLDER_URL, params={"name": folder_name})
    assert resp.status_code == 201, resp.text
    folder = resp.json()
    resp = await client.post(
        UPLOAD_URL,
        files={"file": (f"inner_{suffix}.txt", b"inner", "text/plain")},
        params={"pid": folder["id"]},
    )
    assert resp.status_code == 201, resp.text

    # 批量删除: 2 文件 + 1 目录(混选)
    resp = await client.post(
        BATCH_DELETE_URL, json={"entry_ids": file_ids + [folder["id"]]}
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["deleted"] == 3
    assert result["failed"] == []

    # 全部逻辑删除: 目录列表不可见
    resp = await client.get(LIST_DIR_URL, params={"page": 1, "size": 100})
    names = [it["name"] for it in resp.json()["items"]]
    assert f"batch_a_{suffix}.txt" not in names
    assert folder_name not in names
    for entry_id in file_ids:
        resp = await client.get(ENTRY_URL.format(entry_id=entry_id))
        assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_batch_delete_partial_failure(client):
    """批量删除: 不存在的ID不阻断其余项,失败明细可见"""
    resp = await client.post(
        UPLOAD_URL, files={"file": (f"pf_{os.urandom(4).hex()}.txt", b"pf", "text/plain")}
    )
    assert resp.status_code == 201
    entry_id = resp.json()["id"]

    resp = await client.post(
        BATCH_DELETE_URL,
        json={"entry_ids": [entry_id, "not_exist_id", "another_missing"]},
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["deleted"] == 1
    assert len(result["failed"]) == 2
    failed_ids = {it["id"] for it in result["failed"]}
    assert failed_ids == {"not_exist_id", "another_missing"}
    assert all(it["error"] for it in result["failed"])


@pytest.mark.asyncio
async def test_entry_detail_with_owner(client):
    """条目详情: 含上传用户名/物理存储位置/存储类型/引用计数/标签"""
    resp = await client.post(
        UPLOAD_URL,
        files={"file": (f"detail_{os.urandom(4).hex()}.txt", b"detail content " + os.urandom(8), "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    entry_id = resp.json()["id"]

    resp = await client.get(ENTRY_DETAIL_URL.format(entry_id=entry_id))
    assert resp.status_code == 200, resp.text
    detail = resp.json()
    assert detail["id"] == entry_id
    # 上传用户名(admin 登录用户,昵称优先其次用户名)
    assert detail["owner_name"]
    # 内容元数据(存储类型取自配置,conftest 仅覆盖存储实现实例)
    from common.config.index import conf

    assert detail["physical_storage"]
    assert detail["storage_type"] == str(conf.file_system.storage_type)
    assert detail["ref_count"] == 1
    assert detail["content_status"] == "success"
    # 标签默认空数组
    assert detail["tags"] == []

    # 目录也有详情(无内容元数据)
    resp = await client.post(FOLDER_URL, params={"name": f"detail_dir_{os.urandom(4).hex()}"})
    folder = resp.json()
    resp = await client.get(ENTRY_DETAIL_URL.format(entry_id=folder["id"]))
    assert resp.status_code == 200
    assert resp.json()["is_directory"] is True
    assert resp.json()["physical_storage"] is None

    # 不存在的条目 404
    resp = await client.get(ENTRY_DETAIL_URL.format(entry_id="missing_id"))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_entry_tags_update(client):
    """标签组: 编辑接口更新 tags(文件夹/文件通用),详情与列表同步可见"""
    folder_name = f"tags_dir_{os.urandom(4).hex()}"
    resp = await client.post(FOLDER_URL, params={"name": folder_name})
    assert resp.status_code == 201
    folder = resp.json()
    assert folder["tags"] == []

    # 更新标签组
    tags = ["项目资料", "2026", "重要"]
    resp = await client.put(
        UPDATE_ENTRY_URL.format(entry_id=folder["id"]),
        json={"tags": tags},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["tags"] == tags

    # 详情同步可见
    resp = await client.get(ENTRY_DETAIL_URL.format(entry_id=folder["id"]))
    assert resp.json()["tags"] == tags

    # 列表同步可见
    resp = await client.get(LIST_DIR_URL, params={"page": 1, "size": 100})
    item = next(it for it in resp.json()["items"] if it["id"] == folder["id"])
    assert item["tags"] == tags

    # 清空标签(传空数组)
    resp = await client.put(
        UPDATE_ENTRY_URL.format(entry_id=folder["id"]),
        json={"tags": []},
    )
    assert resp.status_code == 200
    assert resp.json()["tags"] == []

    await client.delete(FOLDER_DELETE_URL.format(folder_id=folder["id"]))
