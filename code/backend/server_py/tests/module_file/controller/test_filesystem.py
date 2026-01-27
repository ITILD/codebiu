import pytest
import aiohttp
from common.config.index import conf
import logging
import time

logger = logging.getLogger(__name__)

filename = "test_upload.txt"
content_type = 'text/plain;'
base_url = f"http://localhost:{conf.server.port}/file/filesystem"
generate_presigned_url_upload_url = f"{base_url}/generate_presigned_url_upload"
# 测试文件内容
text_content = f"""This is a test text file,to test presigned url upload.
upload time: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}
"""
# 将文本内容转换为字节
text_bytes = text_content.encode("utf-8")


@pytest.mark.asyncio
async def test_presigned_url_upload():
    # 验证上传结果
    presigned_url_upload_url = await _generate_presigned_url_upload(filename)
    await _presigned_url_upload(presigned_url_upload_url)


async def _generate_presigned_url_upload(filename: str):
    """
    生成上传预签名URL接口
    """
    async with aiohttp.ClientSession() as session:
        logger.info("Testing generate_presigned_url_upload endpoint...")

        # 准备测试数据
        test_data = {"filename": filename, "content_type": content_type}

        try:
            # 发送POST请求到生成预签名URL的端点
            async with session.post(
                generate_presigned_url_upload_url, json=test_data
            ) as response:
                logger.info(f"Response status: {response.status}")

                # 检查响应状态
                assert response.status == 200, (
                    f"Expected status 200, got {response.status}"
                )

                # 读取响应数据
                response_url = await response.json()

                # 上传测试数据
                logger.info(f"Upload response url: {response_url}")
                return response_url
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise


async def _presigned_url_upload(presigned_url_upload_url: str):
    """
    上传文件到预签名URL接口
    """
    # 上传文件
    async with aiohttp.ClientSession() as session:
        headers = {"Content-Type": content_type}
        async with session.put(
            presigned_url_upload_url, data=text_bytes, headers=headers
        ) as response:
            logger.info(f"Upload response status: {response.status}")
            assert response.status == 200, f"Expected status 200, got {response.status}"


# # 清理上传的文件
# async with session.delete(
#     f"{base_url}/delete_file",
#     json=upload_response,
#     content_type="application/json"
# ) as response:
#     logger.info(f"Upload response data: {await response.read()}")
