# -*- coding: utf-8 -*-
"""module_websearch 接口标准测试
覆盖: GET /websearch/engines 引擎列表;POST /websearch/search 仅参数校验(422)
不真实调用外部搜索引擎(不触达 duckduckgo/tavily/firecrawl 外部服务)
"""

import time

import httpx

BASE = "/websearch"


async def test_list_engines(client: httpx.AsyncClient):
    """引擎列表: 返回全部注册引擎,默认引擎置顶,字段完整"""
    resp = await client.get(f"{BASE}/engines")
    assert resp.status_code == 200, resp.text
    engines = resp.json()
    assert isinstance(engines, list) and engines, "应返回非空引擎列表"

    # 应包含工厂注册的全部引擎
    names = {e["name"] for e in engines}
    assert names == {"duckduckgo", "tavily", "firecrawl"}, f"应包含全部注册引擎: {names}"

    # 默认引擎置顶(仅一个默认)
    defaults = [e for e in engines if e["is_default"]]
    assert len(defaults) == 1, "应有且仅有一个默认引擎"
    assert engines[0]["is_default"] is True, "默认引擎应排在首位"

    # 字段完整性
    for e in engines:
        assert e["display_name"], "每个引擎应有展示名称"
        assert isinstance(e["available"], bool), "每个引擎应有可用标记"
        assert isinstance(e["requires_api_key"], bool), "每个引擎应声明是否需要API Key"


async def test_search_missing_query(client: httpx.AsyncClient):
    """搜索缺少查询词应 422(不触达外部引擎)"""
    resp = await client.post(f"{BASE}/search", json={})
    assert resp.status_code == 422, resp.text


async def test_search_query_too_long(client: httpx.AsyncClient):
    """查询词超过500字符上限应 422(不触达外部引擎)"""
    resp = await client.post(f"{BASE}/search", json={"query": "测" * 501})
    assert resp.status_code == 422, resp.text


async def test_search_invalid_engine(client: httpx.AsyncClient):
    """非法引擎标识应 422(枚举校验,不触达外部引擎)"""
    resp = await client.post(
        f"{BASE}/search",
        json={"query": f"测试_{int(time.time() * 1000)}", "engine": "baidu"},
    )
    assert resp.status_code == 422, resp.text


async def test_search_invalid_limit(client: httpx.AsyncClient):
    """返回条数越界(0 与 31)应 422(不触达外部引擎)"""
    for limit in (0, 31):
        resp = await client.post(
            f"{BASE}/search", json={"query": "测试", "limit": limit}
        )
        assert resp.status_code == 422, f"limit={limit} 应返回422: {resp.text}"
