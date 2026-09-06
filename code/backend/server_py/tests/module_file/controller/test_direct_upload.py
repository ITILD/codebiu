"""module_file 直传(direct)模式 controller 测试

用内存版 FakeS3Storage 模拟 S3 协议存储(零外部依赖),覆盖:
- 上传模式查询(direct)
- 预签名直传全流程: init(凭证+每片URL) -> 模拟浏览器直传 -> complete 对账建条目
- 秒传(init is_existing)
- 直传下载 302 重定向
- 伪造分片清单对账失败
存储替换方式: app.dependency_overrides 覆盖 get_file_service + 替换 service 模块级 storage_config
"""

import hashlib
import logging
import os
from pathlib import Path

import pytest

from module_file.dependencies.filesystem import get_file_service
from module_file.service.filesystem import FileService
from module_file.utils.multi_storage.session.impl.storage_s3 import (
    S3StorageInterface,
)

logger = logging.getLogger(__name__)

BASE = "/file/filesystem"
MULTIPART_INIT_URL = f"{BASE}/multipart/init"
MULTIPART_COMPLETE_URL = f"{BASE}/multipart/{{upload_id}}/complete"
UPLOAD_COMPLETE_URL = f"{BASE}/upload-complete"
UPLOAD_MODE_URL = f"{BASE}/upload-mode"
DOWNLOAD_URL = f"{BASE}/download/{{entry_id}}"
DELETE_FILE_URL = f"{BASE}/files/{{file_id}}"

# 测试用分片大小(与 service 一致)
PART_SIZE = 8 * 1024 * 1024


class FakeS3Storage(S3StorageInterface):
    """内存版 S3 存储模拟(继承 S3 接口使 isinstance 判定为 direct,零外部依赖)"""

    def __init__(self):
        # 不调用 super().__init__(无需真实 S3 配置)
        self.uploads: dict[tuple[str, str], dict[int, tuple[bytes, str]]] = {}
        self.objects: dict[str, bytes] = {}
        self._seq = 0
        self.presign_put_calls: list[dict] = []

    async def create_multipart(
        self, key: str, content_type: str = "application/octet-stream"
    ) -> str:
        self._seq += 1
        uid = f"fake-upload-{self._seq}"
        self.uploads[(key, uid)] = {}
        return uid

    async def presign_put(
        self,
        key: str,
        upload_id: str | None = None,
        part_number: int | None = None,
        expires: int = 3600,
    ) -> str | None:
        self.presign_put_calls.append(
            {"key": key, "upload_id": upload_id, "part_number": part_number}
        )
        return (
            f"https://fake-s3.example/{key}"
            f"?uploadId={upload_id}&partNumber={part_number}"
        )

    async def presign_get(
        self, key: str, expires: int = 3600, download_filename: str | None = None
    ) -> str | None:
        return f"https://fake-s3.example/{key}?download=1"

    async def upload_part(
        self, key: str, upload_id: str, part_number: int, data: bytes
    ) -> dict:
        etag = f'"{hashlib.md5(data).hexdigest()}"'
        self.uploads[(key, upload_id)][part_number] = (data, etag)
        return {"part_number": part_number, "etag": etag, "size": len(data)}

    async def list_parts(self, key: str, upload_id: str) -> list[dict]:
        parts = self.uploads.get((key, upload_id), {})
        return [
            {"part_number": n, "etag": etag, "size": len(data)}
            for n, (data, etag) in sorted(parts.items())
        ]

    async def complete_multipart(
        self,
        key: str,
        upload_id: str,
        parts: list[dict],
        expected_hash: str | None = None,
    ) -> tuple[str, int, str]:
        session = self.uploads.pop((key, upload_id))
        merged = b"".join(
            session[int(p["part_number"])][0]
            for p in sorted(parts, key=lambda x: int(x["part_number"]))
        )
        real_hash = hashlib.sha256(merged).hexdigest()
        final_hash = expected_hash or real_hash
        final_key = f"uploads/20260906/{final_hash}{Path(key).suffix}"
        self.objects[final_key] = merged
        return final_hash, len(merged), final_key

    async def abort_multipart(self, key: str, upload_id: str) -> None:
        self.uploads.pop((key, upload_id), None)

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def load(self, key: str) -> bytes:
        return self.objects[key]

    async def size(self, key: str) -> int:
        return len(self.objects[key])

    async def delete(self, key: str) -> bool:
        return self.objects.pop(key, None) is not None

    async def iter_chunks(self, key: str, chunk_size: int = 8192):
        data = self.objects.get(key, b"")
        for i in range(0, len(data), chunk_size):
            yield data[i : i + chunk_size]


@pytest.fixture
def direct_env(client):
    """direct 模式环境: FakeS3Storage 注入 FileService(继承S3接口,isinstance判定为direct)

    注意: module_file 是 mount 的子应用(FastAPI实例),依赖覆盖必须注册在 module_app 上
    """
    fake = FakeS3Storage()
    from module_file.config.server import module_app

    async def _override():
        return FileService(storage_interface=fake)

    module_app.dependency_overrides[get_file_service] = _override
    yield fake
    module_app.dependency_overrides.pop(get_file_service, None)


@pytest.mark.asyncio
async def test_upload_mode_direct(direct_env, client):
    """s3 存储下 upload-mode 返回 direct"""
    resp = await client.get(UPLOAD_MODE_URL)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["mode"] == "direct"
    assert data["part_size"] == PART_SIZE


@pytest.mark.asyncio
async def test_direct_multipart_flow(direct_env, client):
    """直传全流程: init(每片预签名URL) -> 模拟浏览器直传 -> complete 对账建条目"""
    fake = direct_env
    # 8MB + 4MB 两片
    content = os.urandom(PART_SIZE + PART_SIZE // 2)
    content_hash = hashlib.sha256(content).hexdigest()
    filename = f"direct_{os.urandom(4).hex()}.bin"

    # 1. init: 返回凭证 + 每片预签名URL
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
    assert init["mode"] == "direct"
    assert init["part_size"] == PART_SIZE
    total = 2
    assert len(init["part_urls"]) == total
    assert "partNumber=1" in init["part_urls"][0]
    assert "partNumber=2" in init["part_urls"][1]

    # 2. 模拟浏览器直传(预签名URL的数据面,不经服务端): 直接调 fake.upload_part
    # 从 fake 中找到当前活跃会话(token 不透明,会话已由 init 创建)
    (key, upload_id) = next(iter(fake.uploads))
    parts = []
    for n in range(total):
        chunk = content[n * PART_SIZE : (n + 1) * PART_SIZE]
        part = await fake.upload_part(key, upload_id, n + 1, chunk)
        # 前端读到的 ETag 带引号,complete 提交保持一致
        parts.append(
            {"part_number": part["part_number"], "etag": part["etag"], "size": part["size"]}
        )

    # 3. complete: 服务端对账分片清单并建条目
    resp = await client.post(
        MULTIPART_COMPLETE_URL.format(upload_id=init["upload_id"]),
        json={
            "filename": filename,
            "file_size_bytes": len(content),
            "parts": parts,
        },
    )
    assert resp.status_code == 201, f"complete 失败: {resp.text}"
    entry = resp.json()
    assert entry["content_hash"] == content_hash
    assert entry["file_size_bytes"] == len(content)

    # 清理
    await client.delete(DELETE_FILE_URL.format(file_id=entry["id"]))


@pytest.mark.asyncio
async def test_direct_reconcile_missing_part(direct_env, client):
    """直传对账: 前端提交清单缺片时 complete 失败(400)"""
    fake = direct_env
    content = os.urandom(PART_SIZE + 1024)
    filename = f"recon_{os.urandom(4).hex()}.bin"

    resp = await client.post(
        MULTIPART_INIT_URL,
        json={
            "filename": filename,
            "file_size_bytes": len(content),
            "content_hash": hashlib.sha256(content).hexdigest(),
        },
    )
    init = resp.json()
    (key, upload_id) = next(iter(fake.uploads))
    # 模拟浏览器只传了第 1 片(ETag 真实,避免 ETag 校验先于缺片触发)
    part1 = await fake.upload_part(key, upload_id, 1, content[:PART_SIZE])
    # 但提交清单声称两片都传完
    resp = await client.post(
        MULTIPART_COMPLETE_URL.format(upload_id=init["upload_id"]),
        json={
            "filename": filename,
            "parts": [
                {
                    "part_number": 1,
                    "etag": part1["etag"],
                    "size": PART_SIZE,
                },
                {"part_number": 2, "etag": '"y"', "size": 1024},
            ],
        },
    )
    assert resp.status_code == 400
    assert "未在存储中找到" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_direct_download_302(direct_env, client):
    """direct 模式下载返回 302 重定向到预签名直链"""
    fake = direct_env
    content = os.urandom(1024)
    filename = f"dl_{os.urandom(4).hex()}.bin"

    resp = await client.post(
        MULTIPART_INIT_URL,
        json={
            "filename": filename,
            "file_size_bytes": len(content),
            "content_hash": hashlib.sha256(content).hexdigest(),
        },
    )
    init = resp.json()
    (key, upload_id) = next(iter(fake.uploads))
    parts = [await fake.upload_part(key, upload_id, 1, content)]
    resp = await client.post(
        MULTIPART_COMPLETE_URL.format(upload_id=init["upload_id"]),
        json={
            "filename": filename,
            "file_size_bytes": len(content),
            "parts": [
                {"part_number": p["part_number"], "etag": p["etag"], "size": p["size"]}
                for p in parts
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    entry = resp.json()

    # 下载: 302 -> 预签名直链(浏览器直连对象存储)
    resp = await client.get(DOWNLOAD_URL.format(entry_id=entry["id"]))
    assert resp.status_code == 302
    assert "fake-s3.example" in resp.headers["location"]
    await client.delete(DELETE_FILE_URL.format(file_id=entry["id"]))


@pytest.mark.asyncio
async def test_direct_instant_upload(direct_env, client):
    """直传秒传: 相同内容第二次 init 直接返回 is_existing"""
    content = os.urandom(PART_SIZE + 512)
    content_hash = hashlib.sha256(content).hexdigest()
    fake = direct_env

    # 第一次: 完整直传流程
    resp = await client.post(
        MULTIPART_INIT_URL,
        json={
            "filename": f"instant_a_{os.urandom(4).hex()}.bin",
            "file_size_bytes": len(content),
            "content_hash": content_hash,
        },
    )
    init = resp.json()
    (key, upload_id) = next(iter(fake.uploads))
    parts = [await fake.upload_part(key, upload_id, 1, content)]
    resp = await client.post(
        MULTIPART_COMPLETE_URL.format(upload_id=init["upload_id"]),
        json={
            "filename": "instant_a.bin",
            "file_size_bytes": len(content),
            "parts": [
                {"part_number": p["part_number"], "etag": p["etag"], "size": p["size"]}
                for p in parts
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    first = resp.json()

    # 第二次: 同内容 init -> 秒传
    resp = await client.post(
        MULTIPART_INIT_URL,
        json={
            "filename": f"instant_b_{os.urandom(4).hex()}.bin",
            "file_size_bytes": len(content),
            "content_hash": content_hash,
        },
    )
    init2 = resp.json()
    assert init2["is_existing"] is True
    assert init2["upload_id"] is None

    # 秒传建条目
    resp = await client.post(
        UPLOAD_COMPLETE_URL,
        json={
            "name": "instant_b.bin",
            "content_hash": content_hash,
            "file_size_bytes": len(content),
        },
    )
    assert resp.status_code == 201, resp.text
    second = resp.json()
    assert second["id"] != first["id"]

    for e in (first, second):
        await client.delete(DELETE_FILE_URL.format(file_id=e["id"]))


@pytest.mark.asyncio
async def test_direct_presign_failure_fallback_proxy(direct_env, client):
    """预签名生成失败自动降级为中转: init 返回 proxy,数据面改经服务端,上传仍可完成"""
    fake = direct_env
    content = os.urandom(PART_SIZE)  # 中转单片限制 8MB
    content_hash = hashlib.sha256(content).hexdigest()
    filename = f"fallback_{os.urandom(4).hex()}.bin"

    # 预签名全部返回 None(模拟 S3 签名故障)
    async def _broken_presign(*args, **kwargs):
        return None

    fake.presign_put = _broken_presign

    resp = await client.post(
        MULTIPART_INIT_URL,
        json={
            "filename": filename,
            "file_size_bytes": len(content),
            "content_hash": content_hash,
        },
    )
    assert resp.status_code == 200, resp.text
    init = resp.json()
    # 降级为中转凭证,无预签名 URL
    assert init["mode"] == "proxy"
    assert not init["part_urls"]

    # 中转模式: 分片经服务端 PUT 上传
    upload_id = init["upload_id"]
    resp = await client.put(
        f"{BASE}/multipart/{upload_id}/parts/1",
        content=content,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert resp.status_code == 200, resp.text

    resp = await client.post(
        MULTIPART_COMPLETE_URL.format(upload_id=upload_id),
        json={
            "filename": filename,
            "file_size_bytes": len(content),
            "parts": [{"part_number": 1, "size": len(content)}],
        },
    )
    assert resp.status_code == 201, resp.text
    entry = resp.json()
    assert entry["content_hash"] == content_hash
    await client.delete(DELETE_FILE_URL.format(file_id=entry["id"]))


@pytest.mark.asyncio
async def test_direct_reconcile_etag_mismatch(direct_env, client):
    """直传对账: 前端提交被篡改的 ETag 时 complete 失败(400)"""
    fake = direct_env
    content = os.urandom(1024)
    filename = f"etag_{os.urandom(4).hex()}.bin"

    resp = await client.post(
        MULTIPART_INIT_URL,
        json={
            "filename": filename,
            "file_size_bytes": len(content),
            "content_hash": hashlib.sha256(content).hexdigest(),
        },
    )
    init = resp.json()
    (key, upload_id) = next(iter(fake.uploads))
    await fake.upload_part(key, upload_id, 1, content)
    resp = await client.post(
        MULTIPART_COMPLETE_URL.format(upload_id=init["upload_id"]),
        json={
            "filename": filename,
            "parts": [{"part_number": 1, "etag": '"tampered"', "size": len(content)}],
        },
    )
    assert resp.status_code == 400
    assert "不一致" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_direct_complete_size_mismatch(direct_env, client):
    """直传完成: 声明大小与合并后实际大小不一致时 complete 失败(400)"""
    fake = direct_env
    content = os.urandom(2048)
    filename = f"sizemis_{os.urandom(4).hex()}.bin"

    resp = await client.post(
        MULTIPART_INIT_URL,
        json={
            "filename": filename,
            "file_size_bytes": len(content),
            "content_hash": hashlib.sha256(content).hexdigest(),
        },
    )
    init = resp.json()
    (key, upload_id) = next(iter(fake.uploads))
    part = await fake.upload_part(key, upload_id, 1, content)
    resp = await client.post(
        MULTIPART_COMPLETE_URL.format(upload_id=init["upload_id"]),
        json={
            "filename": filename,
            # 声称比实际多 1 字节
            "file_size_bytes": len(content) + 1,
            "parts": [
                {"part_number": p["part_number"], "etag": p["etag"], "size": p["size"]}
                for p in [part]
            ],
        },
    )
    assert resp.status_code == 400
    assert "不一致" in resp.json()["detail"]
