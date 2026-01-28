import pytest
import aiohttp
from common.config.index import conf
import logging
import time

logger = logging.getLogger(__name__)

filename = "test_upload.txt"
content_type = 'text/plain;'
base_server_url = f"http://localhost:{conf.server.port}"
base_contoller_url = f"{base_server_url}/file/filesystem"

generate_presigned_url_upload_url = f"{base_contoller_url}/generate_presigned_url_upload"
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
    # 上传文件 超时时间15秒
    async with aiohttp.ClientSession() as session:
        # 如果presigned_url_upload_url不以http开头默认拼接base_url
        if not presigned_url_upload_url.startswith("http"):
            presigned_url_upload_url = f"{base_server_url}{presigned_url_upload_url}"
        headers = {"Content-Type": content_type}
        logger.info(f"Upload url: {presigned_url_upload_url}")
        async with session.put(
            presigned_url_upload_url, data=text_bytes, headers=headers, timeout=15
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

# 'http://47.94.107.62:12000/bucket0/test_upload.txt?
# X-Amz-Algorithm=AWS4-HMAC-SHA256&
# X-Amz-Credential=p6gBuroy7EtKJ0acXs2H%2F20260128%2Fus-east-1%2Fs3%2Faws4_request&
# X-Amz-Date=20260128T085525Z&
# X-Amz-Expires=3600&
# X-Amz-SignedHeaders=content-type%3Bhost&
# X-Amz-Signature=1c3eb573261fb93db43b247cff3a16ca14ffbada3b939a50b1eb831f215e3a96'