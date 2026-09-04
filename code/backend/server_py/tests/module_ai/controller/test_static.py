# -*- coding: utf-8 -*-
"""module_ai/static 接口标准测试
覆盖静态首页HTML与静态资源文件访问,以及不存在资源的404分支。

注意: app.py 目前未导入该控制器(static 挂载在 module_template 的 module_app 下),
路由未随应用注册(见测试报告),此处显式导入控制器模块以完成注册后再发起请求。
"""

import time

import httpx

# 显式导入以注册路由(生产 app.py 未导入该控制器)
from module_ai.controller import static as ai_static  # noqa: F401


async def test_static_index(client: httpx.AsyncClient):
    """静态首页 /template/static/ 应返回非空HTML"""
    resp = await client.get("/template/static/")
    assert resp.status_code == 200, resp.text
    assert "text/html" in resp.headers.get("content-type", ""), "应返回HTML内容"
    assert resp.text.strip(), "HTML内容不应为空"


async def test_static_index_file(client: httpx.AsyncClient):
    """静态资源文件 index.html 应可直接访问"""
    resp = await client.get("/template/static/index.html")
    assert resp.status_code == 200, resp.text
    assert "text/html" in resp.headers.get("content-type", ""), "应返回HTML内容"


async def test_static_not_found(client: httpx.AsyncClient):
    """不存在的静态资源应 404"""
    resp = await client.get(f"/template/static/no_such_file_{int(time.time() * 1000)}.html")
    assert resp.status_code == 404, resp.text
