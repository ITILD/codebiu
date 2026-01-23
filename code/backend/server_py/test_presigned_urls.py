"""
测试预签名URL功能的脚本
"""

import asyncio
import aiohttp
import os
from pathlib import Path

# 测试配置
BASE_URL = "http://localhost:8000/filesystem"  # 假设服务器运行在此地址


async def test_presigned_url_functionality():
    """
    测试预签名URL功能
    """
    async with aiohttp.ClientSession() as session:
        print("开始测试预签名URL功能...")
        
        # 1. 测试生成上传预签名URL
        print("\n1. 测试生成上传预签名URL...")
        try:
            async with session.post(
                f"{BASE_URL}/presigned-url",
                params={
                    "file_key": "test_file.txt",
                    "method": "put",
                    "expiration": 3600
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    presigned_url = data.get("presigned_url")
                    print(f"✓ 成功生成上传预签名URL: {presigned_url[:50]}...")
                else:
                    print(f"✗ 生成上传预签名URL失败，状态码: {response.status}")
                    print(await response.text())
        except Exception as e:
            print(f"✗ 生成上传预签名URL时发生错误: {e}")
        
        # 2. 测试生成下载预签名URL
        print("\n2. 测试生成下载预签名URL...")
        try:
            async with session.post(
                f"{BASE_URL}/presigned-url",
                params={
                    "file_key": "test_file.txt",
                    "method": "get",
                    "expiration": 3600
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    presigned_url = data.get("presigned_url")
                    print(f"✓ 成功生成下载预签名URL: {presigned_url[:50]}...")
                else:
                    print(f"✗ 生成下载预签名URL失败，状态码: {response.status}")
                    print(await response.text())
        except Exception as e:
            print(f"✗ 生成下载预签名URL时发生错误: {e}")
        
        # 3. 测试生成删除预签名URL
        print("\n3. 测试生成删除预签名URL...")
        try:
            async with session.post(
                f"{BASE_URL}/presigned-url",
                params={
                    "file_key": "test_file.txt",
                    "method": "delete",
                    "expiration": 3600
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    presigned_url = data.get("presigned_url")
                    print(f"✓ 成功生成删除预签名URL: {presigned_url[:50]}...")
                else:
                    print(f"✗ 生成删除预签名URL失败，状态码: {response.status}")
                    print(await response.text())
        except Exception as e:
            print(f"✗ 生成删除预签名URL时发生错误: {e}")
        
        # 4. 测试文件上传
        print("\n4. 测试文件上传...")
        test_file_content = b"This is a test file content."
        try:
            # 先获取上传预签名URL
            async with session.post(
                f"{BASE_URL}/presigned-url",
                params={
                    "file_key": "uploaded_test_file.txt",
                    "method": "put",
                    "expiration": 3600
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    upload_url = data.get("presigned_url")
                    
                    # 使用预签名URL上传文件
                    async with session.put(
                        upload_url,
                        data=test_file_content
                    ) as upload_response:
                        if upload_response.status in [200, 201, 204]:
                            print("✓ 通过预签名URL成功上传文件")
                        else:
                            print(f"✗ 通过预签名URL上传文件失败，状态码: {upload_response.status}")
                else:
                    print(f"✗ 获取上传预签名URL失败，状态码: {response.status}")
        except Exception as e:
            print(f"✗ 文件上传时发生错误: {e}")
        
        print("\n预签名URL功能测试完成！")


if __name__ == "__main__":
    asyncio.run(test_presigned_url_functionality())