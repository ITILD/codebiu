import pytest
from httpx import ASGITransport, AsyncClient
from module_file.do.filesystem import GeneratePresignedUploadResponse,GeneratePresignedDownloadResponse
import logging
import time
from app import app
from common.config.index import conf
import hashlib
from module_file.utils.multi_storage.do.storage_config import StorageType

logger = logging.getLogger(__name__)

CONTENT_TYPE = "text/plain"
BASE_CONTROLLER_URL = "/file/filesystem"

# 测试URL
GENERATE_PRESIGNED_URL_UPLOAD_URL = (
    f"{BASE_CONTROLLER_URL}/generate_presigned_url_upload"
)
PRESIGNED_URL_UPLOAD_SUCCESS_URL = f"{BASE_CONTROLLER_URL}/presigned_url_upload_success"
GENERATE_PRESIGNED_URL_DOWNLOAD_URL = (
    f"{BASE_CONTROLLER_URL}/generate_presigned_url_download/{{file_id}}"
)
DELETE_FILE_URL = f"{BASE_CONTROLLER_URL}/file/{{file_id}}"


@pytest.mark.asyncio
async def test_object_storage_url():
    """
    测试对象存储的上传、重复上传与删除逻辑（兼容 S3/MinIO/OSS/LocalFS）
    """
    # 准备测试内容
    filename = "test_upload.txt"
    text = f"""This is a test text file for presigned URL upload.
    Upload time: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}
    """
    text_bytes = text.encode("utf-8")
    content_hash = hashlib.sha256(text_bytes).hexdigest()
    file_size = len(text_bytes)

    # === 1. 首次上传 ===
    resp1 = await _generate_presigned_url_upload(filename, text_bytes, content_hash)
    assert resp1.presigned_url, "首次上传应返回有效预签名 URL"
    assert not resp1.is_existing_file, "新文件不应标记为已存在"

    await _upload_to_presigned_url(resp1.presigned_url, text_bytes)
    file_id = await _notify_upload_success(
        name=filename,
        content_hash=content_hash,
        file_size_bytes=file_size,
    )
    assert file_id, "首次上传后应返回有效 file_id"

    # === 2. 下载文件 ===
    resp1_down = await _generate_presigned_url_download(file_id)
    assert resp1_down.presigned_url, "下载URL应成功生成"
    text_content_down = await _download_from_presigned_url(resp1_down.presigned_url)
    assert text_content_down == text, "下载内容应与上传内容一致"

    # === 2. 重复上传（相同内容）===
    repeat_filename = "test_upload_repeat.txt"
    resp2 = await _generate_presigned_url_upload(
        repeat_filename, text_bytes, content_hash
    )
    assert not resp2.presigned_url, "重复内容不应生成新上传 URL"
    assert resp2.is_existing_file, "应识别为已存在文件"

    # 即使是重复文件，仍可创建新元数据记录（不同逻辑路径）
    file_id_repeat = await _notify_upload_success(
        name=f"new_{repeat_filename}",
        content_hash=content_hash,
        file_size_bytes=file_size,
    )
    assert file_id_repeat, "重复上传通知应成功并返回 file_id"

    # === 清理 ===
    await _delete_file(file_id_repeat)
    await _delete_file(file_id)
    # 获取校验


# 带目录级别的上传测试


# --- 辅助函数 ---
async def _generate_presigned_url_upload(
    filename: str, content: bytes, content_hash: str
) -> GeneratePresignedUploadResponse:
    """请求生成预签名上传 URL"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post(
            GENERATE_PRESIGNED_URL_UPLOAD_URL,
            json={
                "filename": filename,
                "content_type": CONTENT_TYPE,
                "content_hash": content_hash,
                "file_size_bytes": len(content),
            },
        )
        assert response.status_code == 200, f"生成预签名 URL 失败: {response.text}"
        return GeneratePresignedUploadResponse.model_validate(response.json())


async def _upload_to_presigned_url(url: str, content: bytes) -> None:
    """将文件内容上传到预签名 URL（支持本地/远程存储）"""
    headers = {"Content-Type": CONTENT_TYPE}
    logger.info(f"Uploading to presigned URL: {url}")

    client_kwargs = {}
    if conf.file_system.storage_type == StorageType.LOCAL:
        # 本地模式 → 使用 ASGI transport 和 base_url
        client_kwargs["transport"] = ASGITransport(app=app)
        client_kwargs["base_url"] = "http://test"

    async with AsyncClient(**client_kwargs) as ac:
        response = await ac.put(url, content=content, headers=headers)

    assert response.status_code == 200, (
        f"上传失败: {response.status_code} - {response.text}"
    )
    logger.info("Upload succeeded")


async def _notify_upload_success(
    name: str,
    content_hash: str,
    file_size_bytes: int,
    logical_path: str = "/todo",
) -> str:
    """通知后端上传完成，创建元数据记录，返回 file_id"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post(
            PRESIGNED_URL_UPLOAD_SUCCESS_URL,
            json={
                "name": name,
                "content_type": CONTENT_TYPE,
                "content_hash": content_hash,
                "file_size_bytes": file_size_bytes,
                "logical_path": logical_path,
            },
        )
        assert response.status_code == 200, f"通知上传成功失败: {response.text}"
        return response.json().get("file_id")  # 假设响应包含 file_id


async def _generate_presigned_url_download(file_id: str) -> GeneratePresignedDownloadResponse:
    """请求生成预签名下载 URL"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get(
            GENERATE_PRESIGNED_URL_DOWNLOAD_URL.format(file_id=file_id)
        )
        assert response.status_code == 200, f"生成预签名 URL 失败: {response.text}"
        return GeneratePresignedDownloadResponse.model_validate(response.json()) # 假设响应包含 presigned_url


async def _download_from_presigned_url(url: str) -> bytes:
    """从预签名 URL 下载文件内容"""
    logger.info(f"Downloading from presigned URL: {url}")

    client_kwargs = {}
    if conf.file_system.storage_type == StorageType.LOCAL:
        # 本地模式 → 使用 ASGI transport 和 base_url
        client_kwargs["transport"] = ASGITransport(app=app)
        client_kwargs["base_url"] = "http://test"
    
    async with AsyncClient(**client_kwargs) as ac:
        response = await ac.get(url)
        assert response.status_code == 200, (
            f"下载失败: {response.status_code} - {response.text}"
        )
        return response.text


async def _delete_file(file_id: str) -> None:
    """删除指定文件"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.delete(DELETE_FILE_URL.format(file_id=file_id))
        assert response.status_code == 204, f"删除文件失败: {response.text}"
