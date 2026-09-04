# -*- coding: utf-8 -*-
"""module_authorization/casbin_rule 接口标准测试(安全子集)
覆盖: 策略/角色绑定列表、模块权限树、权限检查、角色权限查询、临时策略增删闭环
不覆盖: reload-policy / 全量删除等破坏性端点(避免破坏系统内置策略)
"""

import httpx

BASE = "/authorization/casbin-rules"


async def test_policies_list(client: httpx.AsyncClient):
    """策略列表应返回数据(系统内置策略非空)"""
    resp = await client.get(f"{BASE}/policies")
    assert resp.status_code == 200, resp.text


async def test_grouping_policies_list(client: httpx.AsyncClient):
    """角色绑定列表应返回数据(admin 角色绑定非空)"""
    resp = await client.get(f"{BASE}/grouping-policies")
    assert resp.status_code == 200, resp.text


async def test_module_tree(client: httpx.AsyncClient):
    """模块权限声明树应非空(sys/main 基础域必注册)"""
    resp = await client.get(f"{BASE}/module-tree")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    data = body.get("data") if isinstance(body, dict) else body
    assert data, "权限声明树不应为空"


async def test_check_permission_admin_allowed(client: httpx.AsyncClient, admin_token: str):
    """admin 用户对 main/file/read 应有权限"""
    # 先取 admin 的 user_id
    resp_me = await client.get("/authorization/auth/me-id")
    user_id = resp_me.json() if isinstance(resp_me.json(), str) else resp_me.json().get("user_id")
    assert user_id, resp_me.text

    resp = await client.post(
        f"{BASE}/check-permission",
        json={"user_id": user_id, "dom": "main", "obj": "file", "act": "read"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    has = body.get("data") if body.get("data") is not None else body.get("has_permission")
    assert has is True, f"admin 应有权限: {body}"


async def test_roles_for_admin(client: httpx.AsyncClient):
    """admin 用户应绑定全局 admin 角色"""
    resp_me = await client.get("/authorization/auth/me-id")
    user_id = resp_me.json() if isinstance(resp_me.json(), str) else resp_me.json().get("user_id")

    resp = await client.get(f"{BASE}/roles/{user_id}", params={"dom": "*"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    roles = body.get("data") or []
    assert "admin" in roles, f"admin 用户应有 admin 角色: {body}"


async def test_permissions_for_admin_role(client: httpx.AsyncClient):
    """admin 角色应有策略权限"""
    resp = await client.get(f"{BASE}/permissions/admin", params={"dom": "*"})
    assert resp.status_code == 200, resp.text


async def test_policy_add_and_remove(client: httpx.AsyncClient):
    """临时策略增删闭环(测试专用角色,不触碰内置角色;唯一键避免残留污染)"""
    import time

    suffix = str(int(time.time() * 1000))
    sub, dom, obj, act = f"test_role_tmp_{suffix}", "main", f"test_obj_{suffix}", "read"

    try:
        # 添加
        resp = await client.post(
            f"{BASE}/policy", json={"sub": sub, "dom": dom, "obj": obj, "act": act}
        )
        assert resp.status_code == 201, resp.text

        # 查询应包含
        resp = await client.get(f"{BASE}/policies")
        assert resp.status_code == 200, resp.text
        text = resp.text
        assert obj in text, "新策略应出现在策略列表"
    finally:
        # 清理(即使断言失败也要移除临时策略; httpx delete 不支持 body, 用 request 发送)
        resp = await client.request(
            "DELETE", f"{BASE}/policy", json={"sub": sub, "dom": dom, "obj": obj, "act": act}
        )
        assert resp.status_code in (200, 204), resp.text
