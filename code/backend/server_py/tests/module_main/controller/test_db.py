# -*- coding: utf-8 -*-
"""module_main/db 数据库检查接口测试
覆盖: /db/create 建表端点; /db/reset 为破坏性接口, 跳过并说明原因
"""

import httpx
import pytest

BASE = "/db"


async def test_db_create(client: httpx.AsyncClient):
    """创建所有未创建的数据库表: 接口声明 201, 幂等操作可安全重复执行"""
    resp = await client.get(f"{BASE}/create")
    assert resp.status_code == 201, f"应返回201: {resp.status_code} {resp.text}"
    # 服务层返回的 detail 中带成功消息(以实际接口行为为准)
    assert "success" in resp.text.lower(), f"响应应包含成功消息: {resp.text}"


@pytest.mark.skip(
    reason="破坏性接口: /db/reset 会 drop_all+create_all 清空全部表"
    "(含管理员账号/casbin规则), 执行后会使会话级管理员令牌失效,"
    "导致本测试会话内后续所有用例失败, 故不在自动化中执行"
)
async def test_db_reset(client: httpx.AsyncClient):
    """重置所有数据库表(破坏性: 清空数据, 仅人工环境验证)"""
    resp = await client.get(f"{BASE}/reset")
    assert resp.status_code == 201, f"应返回201: {resp.status_code} {resp.text}"
