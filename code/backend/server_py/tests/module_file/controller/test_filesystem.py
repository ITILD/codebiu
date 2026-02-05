import pytest
import aiohttp
from fastapi.testclient import TestClient
from module_file.do.filesystem import GeneratePresignedUploadResponse
import logging
import time
from app import app
from common.config.index import conf
import hashlib

logger = logging.getLogger(__name__)


content_type = "text/plain"
base_controller_url = "/file/filesystem"  # TestClient 不需要 base URL

generate_presigned_url_upload_url = (
    f"{base_controller_url}/generate_presigned_url_upload"
)


@pytest.fixture(scope="module")
def client():
    """提供 TestClient 实例"""
    return TestClient(app)


@pytest.mark.asyncio
async def test_object_storage_url(client: TestClient):
    """
    测试对象存储URL
    """
    # 测试文件内容
    filename = "test_upload.txt"
    text_content_new = f"""This is a test text file, to test presigned url upload.
    upload time: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}
    """
    text_bytes_new = text_content_new.encode("utf-8")
    # 1. 初次上传
    # 1.1 验证上传结果
    generate_presigned_upload_response: GeneratePresignedUploadResponse = (
        await _generate_presigned_url_upload(
            client, filename, text_bytes_new
        )
    )
    
    # 1.2 上传文件到预签名 URL（这是外部服务，必须用真实 HTTP 客户端）
    upload_success = await _presigned_url_upload(
        client, generate_presigned_upload_response.presigned_url, text_bytes_new
    )
    # 通知后端对象/本地存储完成 执行文件夹业务逻辑
    if upload_success:
        pass
    
    # # 2. 验证重复上传
    # # 2.1 验证上传结果
    # filename = "test_upload_repeat.txt"
    # generate_presigned_upload_response: GeneratePresignedUploadResponse = (
    #     await _generate_presigned_url_upload(
    #         client, filename, text_bytes_new
    #     )
    # )
    # assert (
    #     not generate_presigned_upload_response.presigned_url
    #     and generate_presigned_upload_response.is_existing_file
    # ), "重复上传文件失败,未发现重复文件"

    # # 2.2 通知后端对象/本地存储完成 执行文件夹业务逻辑
    # # if upload_success:
    # #     pass


async def _generate_presigned_url_upload(client: TestClient, filename: str, text_bytes: bytes):
    """
    测试预签名URL上传/下载和兼容s3删除文件
    """
    content_hash = hashlib.md5(text_bytes).hexdigest()
    # 1. 调用本地 FastAPI 接口生成预签名 URL（使用 TestClient）
    response = client.post(
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
    client: TestClient, presigned_url_upload_url: str, text_bytes: bytes
) -> bool:
    """
    上传文件到预签名URL（外部存储，如 S3）
    使用同步 requests，因为 TestClient 不处理外部 URL
    """
    headers = {"Content-Type": content_type}
    logger.info(f"Uploading to presigned URL: {presigned_url_upload_url}")
    response_result = None
    if conf.file_system.storage_type == "s3":
        async with aiohttp.ClientSession() as session:
            async with session.put(
                presigned_url_upload_url, data=text_bytes, headers=headers, timeout=15
            ) as response:
                response_result = response
                logger.info(f"Upload response status: {response.status}")
                assert response.status == 200, (
                    f"Expected status 200, got {response.status}"
                )
    elif conf.file_system.storage_type == "local":
        response_result = client.put(
            presigned_url_upload_url, content=text_bytes, headers=headers
        )
        assert response_result.status_code == 200, (
            f"Failed to upload file to presigned URL: {response_result.text}"
        )

    logger.info(f"Upload success: {response_result}")

    return True
