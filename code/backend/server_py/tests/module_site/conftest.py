# -*- coding: utf-8 -*-
"""module_site 测试共享设施(个人小站: 博客/备忘/记账 三条业务线)

约定(与既有模块测试一致):
- 管理员走完整 JWT+casbin 链路(父级 conftest 的 client/admin_headers)
- 归属隔离: 通过 site_grant fixture 给普通用户临时授予 site 域 casbin 策略,
  fixture 结束自动回收
- 权限收紧: site 模块 default_policies=[] → 普通用户 403, 匿名 401
"""

import pytest_asyncio

# casbin 策略接口(授予/回收普通用户 site 域权限, 用于隔离性验证)
POLICY_API = "/authorization/casbin-rules/policy"
ME_ID_API = "/authorization/auth/me-id"


@pytest_asyncio.fixture
async def site_user(normal_user: dict) -> dict:
    """普通用户信息(附 user_id, 供策略授权/归属隔离测试)"""
    from httpx import ASGITransport, AsyncClient

    from app import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=normal_user["headers"],
    ) as ac:
        resp = await ac.get(ME_ID_API)
        assert resp.status_code == 200, f"获取用户ID失败: {resp.text}"
        user_id = resp.json()
    return {**normal_user, "user_id": user_id}


@pytest_asyncio.fixture
async def site_grant(client):
    """casbin 直连策略授权器: await site_grant(user_id, obj, act)

    - 为指定用户添加 (site, obj, act) 策略
    - fixture 结束时自动回收本次添加的全部策略(幂等)
    """
    added: list[tuple[str, str, str]] = []

    async def _grant(user_id: str, obj: str, act: str) -> None:
        # 先尝试回收可能的历史残留策略(幂等, 404 忽略), 再授予
        await client.request(
            "DELETE",
            POLICY_API,
            json={"sub": user_id, "dom": "site", "obj": obj, "act": act},
        )
        resp = await client.post(
            POLICY_API, json={"sub": user_id, "dom": "site", "obj": obj, "act": act}
        )
        assert resp.status_code == 201, f"授权失败: {resp.text}"
        added.append((user_id, obj, act))

    yield _grant

    # teardown: 回收策略(幂等, 404 忽略)
    # 注: httpx 的 delete() 不支持 json 参数, 统一用 request("DELETE", json=...)
    for user_id, obj, act in added:
        resp = await client.request(
            "DELETE",
            POLICY_API,
            json={"sub": user_id, "dom": "site", "obj": obj, "act": act},
        )
        assert resp.status_code in (200, 404), f"回收授权失败: {resp.text}"
