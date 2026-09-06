# -*- coding: utf-8 -*-
"""module_site 博客业务线接口测试(/site/blog/posts)

覆盖: markdown/url 两种来源 CRUD、分页过滤、发布可见性(草稿仅作者可见)、
归属隔离、权限收紧(403/401)
"""

import time

import httpx

BASE = "/site/blog/posts"


def _suffix() -> str:
    """时间戳唯一后缀, 避免重复执行/并发时数据串扰"""
    return str(int(time.time() * 1000))


async def test_blog_post_crud_flow(client: httpx.AsyncClient):
    """markdown 文章 创建→查询→更新→删除 全流程"""
    suffix = _suffix()
    title = f"测试文章_{suffix}"
    created_id = None
    try:
        # 创建(默认草稿/markdown 来源)
        resp = await client.post(
            BASE,
            json={"title": title, "source_type": "markdown", "content": "# 标题\n\n正文内容"},
        )
        assert resp.status_code == 201, resp.text
        created_id = resp.json()
        assert isinstance(created_id, str) and created_id, f"创建应返回ID字符串: {created_id}"

        # 查询单个
        resp = await client.get(f"{BASE}/{created_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["title"] == title
        assert body["source_type"] == "markdown"
        assert body["status"] == "draft", "默认状态应为草稿"
        assert "正文内容" in body["content"]

        # 更新(改名/改正文/发布)
        new_title = f"改名文章_{suffix}"
        resp = await client.put(
            f"{BASE}/{created_id}",
            json={"title": new_title, "content": "更新后的正文", "status": "published"},
        )
        assert resp.status_code == 204, resp.text

        resp = await client.get(f"{BASE}/{created_id}")
        body = resp.json()
        assert body["title"] == new_title
        assert body["status"] == "published"
    finally:
        if created_id:
            await client.delete(f"{BASE}/{created_id}")


async def test_blog_post_delete(client: httpx.AsyncClient):
    """删除后查询 → 404"""
    suffix = _suffix()
    resp = await client.post(BASE, json={"title": f"待删文章_{suffix}", "content": "x"})
    assert resp.status_code == 201, resp.text
    created_id = resp.json()

    resp = await client.delete(f"{BASE}/{created_id}")
    assert resp.status_code == 204, resp.text

    resp = await client.get(f"{BASE}/{created_id}")
    assert resp.status_code == 404, resp.text

    # 重复删除 → 404
    resp = await client.delete(f"{BASE}/{created_id}")
    assert resp.status_code == 404, resp.text


async def test_blog_post_url_source(client: httpx.AsyncClient):
    """url 来源文章(关联外链发布) + source_type 过滤"""
    suffix = _suffix()
    title = f"外链文章_{suffix}"
    created_id = None
    try:
        resp = await client.post(
            BASE,
            json={
                "title": title,
                "source_type": "url",
                "url": "https://example.com/post/1",
                "category": "转载",
            },
        )
        assert resp.status_code == 201, resp.text
        created_id = resp.json()

        resp = await client.get(f"{BASE}/{created_id}")
        body = resp.json()
        assert body["source_type"] == "url"
        assert body["url"] == "https://example.com/post/1"

        # 来源过滤: source_type=url 应包含该文章
        resp = await client.get(
            f"{BASE}/list", params={"page": 1, "size": 50, "source_type": "url", "title": title}
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert any(item["id"] == created_id for item in items), "url 过滤应包含该文章"

        # 标题模糊过滤
        resp = await client.get(
            f"{BASE}/list", params={"page": 1, "size": 50, "title": title}
        )
        assert any(item["id"] == created_id for item in resp.json()["items"])
    finally:
        if created_id:
            await client.delete(f"{BASE}/{created_id}")


async def test_blog_post_publish_visibility(
    client: httpx.AsyncClient, site_user: dict, site_grant
):
    """发布可见性: 草稿仅作者可见, 已发布文章对持有 read 权限的用户可见"""
    suffix = _suffix()
    title = f"可见性文章_{suffix}"
    created_id = None
    user_id = site_user["user_id"]
    try:
        resp = await client.post(BASE, json={"title": title, "content": "可见性正文"})
        assert resp.status_code == 201, resp.text
        created_id = resp.json()

        # 授予普通用户 blog read 权限(fixture 结束自动回收)
        await site_grant(user_id, "blog", "read")

        # 草稿对非作者不可见 → 404
        resp = await client.get(f"{BASE}/{created_id}", headers=site_user["headers"])
        assert resp.status_code == 404, f"草稿对非作者应不可见: {resp.text}"

        # 展示列表不含草稿
        resp = await client.get(
            f"{BASE}/view/list",
            params={"page": 1, "size": 50, "keyword": title},
            headers=site_user["headers"],
        )
        assert resp.status_code == 200, resp.text
        assert all(item["id"] != created_id for item in resp.json()["items"])

        # 作者发布
        resp = await client.put(f"{BASE}/{created_id}", json={"status": "published"})
        assert resp.status_code == 204, resp.text

        # 已发布后非作者可见
        resp = await client.get(f"{BASE}/{created_id}", headers=site_user["headers"])
        assert resp.status_code == 200, resp.text

        # 展示列表包含已发布文章
        resp = await client.get(
            f"{BASE}/view/list",
            params={"page": 1, "size": 50, "keyword": title},
            headers=site_user["headers"],
        )
        items = resp.json()["items"]
        assert any(item["id"] == created_id for item in items), "展示列表应包含已发布文章"
    finally:
        if created_id:
            await client.delete(f"{BASE}/{created_id}")


async def test_blog_post_permission_denied(
    client: httpx.AsyncClient, site_user: dict, anon_client: httpx.AsyncClient
):
    """权限收紧: default_policies=[] → 普通用户 403, 匿名 401"""
    # 普通用户未授权 → 403
    resp = await client.post(
        BASE, json={"title": "无权限文章"}, headers=site_user["headers"]
    )
    assert resp.status_code == 403, resp.text

    resp = await client.get(f"{BASE}/list", headers=site_user["headers"])
    assert resp.status_code == 403, resp.text

    # 匿名 → 401
    resp = await anon_client.get(f"{BASE}/view/list")
    assert resp.status_code == 401, resp.text


async def test_blog_post_validation(client: httpx.AsyncClient):
    """参数校验: 缺少必填的 title → 422"""
    resp = await client.post(BASE, json={"content": "没有标题"})
    assert resp.status_code == 422, resp.text
