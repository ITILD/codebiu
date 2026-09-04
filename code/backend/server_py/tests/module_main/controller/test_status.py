# -*- coding: utf-8 -*-
"""module_main/status 服务器状态检查接口测试
覆盖: 状态缓存/主机型号/硬件状态/网络状态/挂载路由列表
说明: 这些端点均为只读检查, 无鉴权依赖, 使用管理员客户端访问
"""

import httpx

BASE = "/server-status"


async def test_sys_info(client: httpx.AsyncClient):
    """获取主机型号: 应返回平台标识(PlatformId 枚举, 如 win-x64)"""
    resp = await client.get(f"{BASE}/sys-info")
    assert resp.status_code == 200, resp.text
    assert resp.text.strip(), "应返回非空平台标识"


async def test_hardware_status(client: httpx.AsyncClient):
    """获取硬件状态: 应返回 JSON 对象"""
    resp = await client.get(f"{BASE}/hardware-status")
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), dict), "硬件状态应为JSON对象"


async def test_status_cache(client: httpx.AsyncClient):
    """获取主机状态60秒缓存: 应包含 hardware 与 network 字段"""
    resp = await client.get(f"{BASE}/cache")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "hardware" in body, f"应包含hardware字段: {body}"
    assert "network" in body, f"应包含network字段: {body}"


async def test_network_status(client: httpx.AsyncClient):
    """获取网络状态: 应返回列表, 每项包含 url 与 connect_success"""
    resp = await client.get(f"{BASE}/network-status")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list), "网络状态应为列表"
    if body:  # 无外网环境可能返回空列表, 不强求非空
        for item in body:
            assert "url" in item, f"每项应包含url: {item}"
            assert "connect_success" in item, f"每项应包含connect_success: {item}"


async def test_mount_count(client: httpx.AsyncClient):
    """查看app挂载路由: 应返回挂载路径列表"""
    resp = await client.get(f"{BASE}/mount-count")
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list), "挂载路由应为列表"
