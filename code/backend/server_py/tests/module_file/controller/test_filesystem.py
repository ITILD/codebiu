import pytest
from httpx import ASGITransport, AsyncClient
from module_file.do.filesystem import GeneratePresignedUploadResponse
import logging
import time
from app import app
from common.config.index import conf
import hashlib
from module_file.utils.multi_storage.do.storage_config import StorageType

logger = logging.getLogger(__name__)


content_type = "text/plain"
base_controller_url = "/file/filesystem"

generate_presigned_url_upload_url = (
    f"{base_controller_url}/generate_presigned_url_upload"
)

presigned_url_upload_success_url = f"{base_controller_url}/presigned_url_upload_success"


@pytest.mark.asyncio
async def test_object_storage_url():
    """
    测试对象存储URL
    """
    # 测试文件内容
    filename = "test_upload.txt"
    text_content_new = f"""This is a test text file, to test presigned url upload.
    upload time: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}
    """
    text_bytes_new = text_content_new.encode("utf-8")
    content_hash = hashlib.md5(text_bytes_new).hexdigest()
    # 1. 初次上传
    # 1.1 验证上传结果
    generate_presigned_upload_response: GeneratePresignedUploadResponse = (
        await _generate_presigned_url_upload(filename, text_bytes_new, content_hash)
    )

    # 1.2 上传文件到预签名 URL（这是外部服务，必须用真实 HTTP 客户端）
    upload_success = await _presigned_url_upload(
        generate_presigned_upload_response.presigned_url, text_bytes_new
    )
    # 通知后端对象/本地存储完成 执行文件夹业务逻辑
    await _presigned_url_upload_success(
        filename,
        content_hash,
        generate_presigned_upload_response.physical_storage,
        len(text_bytes_new),
    )

    # # 2. 验证重复上传
    # 2.1 验证上传结果
    filename = "test_upload_repeat.txt"
    generate_presigned_upload_response: GeneratePresignedUploadResponse = (
        await _generate_presigned_url_upload(filename, text_bytes_new, content_hash)
    )
    assert (
        not generate_presigned_upload_response.presigned_url
        and generate_presigned_upload_response.is_existing_file
    ), "重复上传文件失败,未发现重复文件"

    # 2.2 通知后端对象/本地存储完成 执行重复文件业务逻辑
    # 通知后端对象/本地存储完成 执行文件夹业务逻辑
    if generate_presigned_upload_response.is_existing_file:
        await _presigned_url_upload_success(
            f"new_{filename}",
            content_hash,
            generate_presigned_upload_response.physical_storage,
            len(text_bytes_new),
        )


async def _generate_presigned_url_upload(
    filename: str, text_bytes: bytes, content_hash: str
):
    """
    测试预签名URL上传/下载和兼容s3删除文件
    """

    # 1. 调用本地 FastAPI 接口生成预签名 URL（使用 TestClient）
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post(
            generate_presigned_url_upload_url,
            # 准备测试数据 from module_file.do.filesystem import GeneratePresignedUrlRequest
            json={
                "filename": filename,
                "content_type": content_type,
                "content_hash": content_hash,
                "file_size_bytes": len(text_bytes),
            },
        )
        assert response.status_code == 200, (
            f"Failed to generate presigned URL: {response.text}"
        )

        generate_presigned_upload_response: GeneratePresignedUploadResponse = (
            GeneratePresignedUploadResponse.model_validate(response.json())
        )
        logger.info(
            f"Upload response url: {generate_presigned_upload_response.presigned_url}"
        )
        return generate_presigned_upload_response


async def _presigned_url_upload(
    presigned_url_upload_url: str, text_bytes: bytes
) -> bool:
    """
    上传文件到预签名URL（外部存储，如 S3 或本地测试）
    """
    headers = {"Content-Type": "application/octet-stream"}
    logger.info(f"Uploading to presigned URL: {presigned_url_upload_url}")

    if conf.file_system.storage_type == StorageType.LOCAL:
        transport = ASGITransport(app=app)
        base_url = "http://test"
    else:  # 默认视为 S3 或其他外部存储
        transport = None
        base_url = None

    async with AsyncClient(transport=transport, base_url=base_url) as ac:
        response = await ac.put(
            presigned_url_upload_url, content=text_bytes, headers=headers
        )

    assert response.status_code == 200, (
        f"Upload failed: {response.status_code} - {response.text}"
    )
    logger.info(f"Upload success: status={response.status_code}")
    return True


async def _presigned_url_upload_success(
    name: str,
    content_hash: str,
    physical_storage: str,
    file_size_bytes: int,
    pid: str = None,
) -> bool:
    """
    通知后端对象/本地存储完成,新增元数据
    :param content_hash: 文件内容哈希值
    :param logical_path: 文件逻辑路径
    :param physical_storage: 文件物理存储相对位置
    :param file_size_bytes: 文件大小(字节)
    :return: 是否通知成功
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post(
            presigned_url_upload_success_url,
            # 准备测试数据 from module_file.do.filesystem import GeneratePresignedUrlRequest
            json={
                "name": name,
                "content_type": content_type,
                "content_hash": content_hash,
                "file_size_bytes": file_size_bytes,
                "physical_storage": physical_storage,
            },
        )
        assert response.status_code == 200, (
            f"Failed to generate presigned URL: {response.text}"
        )
