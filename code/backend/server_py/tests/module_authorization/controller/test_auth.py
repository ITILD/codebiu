# -*- coding: utf-8 -*-
"""module_authorization/auth 接口标准测试
覆盖: 登录/OAuth2登录/注册/me/me-id/me-permissions/刷新/登出/401场景
"""

import time
import uuid

import httpx

BASE = "/authorization/auth"


async def test_login_ok(client: httpx.AsyncClient):
    """管理员正常登录,返回双令牌与用户信息"""
    resp = await client.post(
        f"{BASE}/login", data={"username": "admin", "password": "admin123"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tokens"]["access"]["token"], "应返回访问令牌"
    assert body["tokens"]["refresh"]["token"], "应返回刷新令牌"
    assert body["user"]["username"] == "admin"


async def test_login_wrong_password(client: httpx.AsyncClient):
    """错误密码登录应 401"""
    resp = await client.post(
        f"{BASE}/login", data={"username": "admin", "password": "wrong-password"}
    )
    assert resp.status_code == 401, resp.text


async def test_login_oauth2_token(client: httpx.AsyncClient):
    """OAuth2 标准端点应返回 bearer 格式令牌(Swagger Authorize 用)"""
    resp = await client.post(
        f"{BASE}/token", data={"username": "admin", "password": "admin123"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"], "应返回 access_token"
    assert body["token_type"] == "bearer"


async def test_me(client: httpx.AsyncClient):
    """获取当前登录用户信息"""
    resp = await client.get(f"{BASE}/me")
    assert resp.status_code == 200, resp.text
    assert resp.json()["username"] == "admin"


async def test_me_id(client: httpx.AsyncClient):
    """获取当前登录用户ID(纯字符串)"""
    resp = await client.get(f"{BASE}/me-id")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    uid = body if isinstance(body, str) else body.get("user_id") or body.get("id")
    assert uid, "应返回非空用户ID"


async def test_me_permissions(client: httpx.AsyncClient):
    """获取当前用户角色与权限码"""
    resp = await client.get(f"{BASE}/me-permissions")
    assert resp.status_code == 200, resp.text


async def test_me_without_token(anon_client: httpx.AsyncClient):
    """无令牌访问受保护端点应 401"""
    resp = await anon_client.get(f"{BASE}/me")
    assert resp.status_code == 401, resp.text


async def test_register_and_cleanup(client: httpx.AsyncClient):
    """注册新用户成功,并清理测试用户"""
    username = f"test_reg_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    resp = await client.post(
        f"{BASE}/register",
        json={"username": username, "password": "Test@123456"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["username"] == username, "注册应返回新用户信息"
    assert body["tokens"]["access"]["token"], "注册应自动登录返回令牌"

    # 清理: 删除测试用户
    user_id = body["user"]["id"]
    resp_del = await client.delete(f"/authorization/users/{user_id}")
    assert resp_del.status_code in (200, 204), resp_del.text


async def test_refresh_token(client: httpx.AsyncClient):
    """用刷新令牌换取新的访问令牌"""
    login = (await client.post(
        f"{BASE}/login", data={"username": "admin", "password": "admin123"}
    )).json()
    refresh_token = login["tokens"]["refresh"]["token"]
    resp = await client.post(f"{BASE}/refresh", json={"token_refresh": refresh_token})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token"], "应返回新访问令牌"


async def test_logout_invalidates_token(client: httpx.AsyncClient):
    """登出后原访问令牌立即失效(独立登录的令牌,不影响其他用例)"""
    # 独立登录一份新令牌用于登出
    login = (await client.post(
        f"{BASE}/login", data={"username": "admin", "password": "admin123"}
    )).json()
    tokens = login["tokens"]
    headers = {"Authorization": f"Bearer {tokens['access']['token']}"}

    resp = await client.post(
        f"{BASE}/logout",
        headers=headers,
        json={
            "token_access": tokens["access"]["token"],
            "token_refresh": tokens["refresh"]["token"],
            "token_refresh_id": tokens["refresh"]["token_id"],
        },
    )
    assert resp.status_code == 200, resp.text

    # 原访问令牌应已被拉黑
    resp_me = await client.get(f"{BASE}/me", headers=headers)
    assert resp_me.status_code == 401, "登出后原令牌应失效"


async def test_update_my_profile(client: httpx.AsyncClient):
    """自助更新个人资料(昵称/邮箱),无需管理员权限"""
    resp = await client.put(
        f"{BASE}/me",
        json={"nickname": "自助昵称", "email": "self_profile@example.com"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["nickname"] == "自助昵称"
    assert body["email"] == "self_profile@example.com"


async def test_update_my_profile_without_token(anon_client: httpx.AsyncClient):
    """无令牌更新个人资料应 401"""
    resp = await anon_client.put(f"{BASE}/me", json={"nickname": "x"})
    assert resp.status_code == 401, resp.text


async def test_change_my_password_flow(client: httpx.AsyncClient):
    """自助修改密码全流程: 注册临时用户→改密→旧密码失效/新密码可登录→清理"""
    username = f"test_pwd_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    # 注册临时用户(注册响应携带该用户自己的令牌)
    reg = (await client.post(
        f"{BASE}/register", json={"username": username, "password": "Test@123456"}
    )).json()
    assert reg["user"]["username"] == username, resp_text_ok(reg)
    user_headers = {"Authorization": f"Bearer {reg['tokens']['access']['token']}"}

    try:
        # 旧密码错误应 400
        resp = await client.put(
            f"{BASE}/me/password",
            headers=user_headers,
            json={"old_password": "WrongOld@123", "new_password": "NewPass@456"},
        )
        assert resp.status_code == 400, resp.text

        # 正确修改密码(204)
        resp = await client.put(
            f"{BASE}/me/password",
            headers=user_headers,
            json={"old_password": "Test@123456", "new_password": "NewPass@456"},
        )
        assert resp.status_code == 204, resp.text

        # 旧密码登录失败
        resp = await client.post(
            f"{BASE}/login", data={"username": username, "password": "Test@123456"}
        )
        assert resp.status_code == 401, resp.text

        # 新密码登录成功
        resp = await client.post(
            f"{BASE}/login", data={"username": username, "password": "NewPass@456"}
        )
        assert resp.status_code == 200, resp.text
    finally:
        # 清理临时用户
        await client.delete(f"/authorization/users/{reg['user']['id']}")


def resp_text_ok(body: dict) -> str:
    """注册响应断言辅助(失败时输出响应体)"""
    return str(body)

# ==================== 头像上传(统一文件服务存储) ====================
# 头像经 FileService 存入虚拟目录 /用户头像/<用户ID>/(source_module='avatar',
# 文件管理可见但只读), 下载走 /file/filesystem/download/{entry_id} 且允许匿名访问
# 注: 内容每次运行唯一 —— 统一存储按内容哈希去重, 固定内容会命中持久库中
# 历史运行的内容记录(其物理文件已随临时存储清理)导致下载404假失败

import uuid as _uuid

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + f"fake-png-{_uuid.uuid4().hex}".encode()


def _assert_avatar_downloadable(resp: httpx.Response, content: bytes, label: str):
    """下载断言(存储类型无关): local流式返回200且内容一致; S3协议返回302预签名直链"""
    assert resp.status_code in (200, 302), f"{label}: {resp.status_code} {resp.text}"
    if resp.status_code == 200:
        assert resp.content == content, f"{label}: 下载内容应与上传一致"


async def test_upload_my_avatar_ok(client: httpx.AsyncClient, anon_client: httpx.AsyncClient):
    """上传头像成功: 返回下载路径与条目ID, me 同步更新, 匿名可下载"""
    content = PNG_BYTES + b"-ok"
    resp = await client.post(
        f"{BASE}/me/avatar",
        files={"file": (f"avatar_{uuid.uuid4().hex[:6]}.png", content, "image/png")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    entry_id = body["entry_id"]
    assert entry_id, "应返回文件条目ID"
    assert body["avatar"].endswith(f"/file/filesystem/download/{entry_id}"), "头像字段应为下载路径"

    # me 已同步新头像
    me = (await client.get(f"{BASE}/me")).json()
    assert me["avatar"] == body["avatar"], "用户头像字段应回写为下载路径"

    # 匿名下载放行(avatar 来源条目)
    resp_dl = await anon_client.get(f"/file/filesystem/download/{entry_id}")
    _assert_avatar_downloadable(resp_dl, content, "avatar 条目应允许匿名下载")


async def test_upload_my_avatar_reupload_cleans_old(client: httpx.AsyncClient, anon_client: httpx.AsyncClient):
    """重复上传: 新头像生效, 旧头像条目被清理(下载404)"""
    resp_first = await client.post(
        f"{BASE}/me/avatar",
        files={"file": (f"avatar_first_{uuid.uuid4().hex[:6]}.png", PNG_BYTES + b"-v1", "image/png")},
    )
    assert resp_first.status_code == 200, resp_first.text
    first = resp_first.json()
    resp_second = await client.post(
        f"{BASE}/me/avatar",
        files={"file": (f"avatar_second_{uuid.uuid4().hex[:6]}.png", PNG_BYTES + b"-v2", "image/png")},
    )
    assert resp_second.status_code == 200, resp_second.text
    second = resp_second.json()
    assert second["entry_id"] != first["entry_id"], "两次上传应生成不同条目"

    resp_old = await anon_client.get(f"/file/filesystem/download/{first['entry_id']}")
    assert resp_old.status_code == 404, "旧头像条目应被清理(404)"
    resp_new = await anon_client.get(f"/file/filesystem/download/{second['entry_id']}")
    _assert_avatar_downloadable(resp_new, PNG_BYTES + b"-v2", "新头像条目应可下载")


async def test_upload_my_avatar_invalid_ext(client: httpx.AsyncClient):
    """非图片格式应 400"""
    resp = await client.post(
        f"{BASE}/me/avatar",
        files={"file": ("avatar_fake.txt", b"plain text", "text/plain")},
    )
    assert resp.status_code == 400, resp.text
    assert "格式" in resp.json()["detail"], "错误信息应提示格式不允许"


async def test_upload_my_avatar_requires_login(anon_client: httpx.AsyncClient):
    """未登录上传头像应 401"""
    resp = await anon_client.post(
        f"{BASE}/me/avatar",
        files={"file": ("avatar.png", PNG_BYTES, "image/png")},
    )
    assert resp.status_code == 401, resp.text

async def test_avatar_entry_readonly_in_file_module(client: httpx.AsyncClient):
    """业务条目只读守卫: avatar 条目在文件管理模块中不可改/删(400), 下载不受影响

    头像等业务条目由业务模块管理, 文件管理端点注入 strict_business_guard 服务拦截写操作
    """
    content = PNG_BYTES + b"-guard"
    resp_guard = await client.post(
        f"{BASE}/me/avatar",
        files={"file": (f"guard_{uuid.uuid4().hex[:6]}.png", content, "image/png")},
    )
    assert resp_guard.status_code == 200, resp_guard.text
    entry_id = resp_guard.json()["entry_id"]

    # 文件管理更新条目 → 拦截(400, 提示业务模块管理)
    resp = await client.put(
        f"/file/filesystem/entries/{entry_id}", json={"name": "renamed.png"}
    )
    assert resp.status_code == 400, resp.text
    assert "业务模块" in resp.json()["detail"], "拦截信息应提示到业务模块操作"

    # 文件管理删除文件 → 拦截(400)
    resp = await client.delete(f"/file/filesystem/files/{entry_id}")
    assert resp.status_code == 400, resp.text

    # 下载不受守卫影响
    resp = await client.get(f"/file/filesystem/download/{entry_id}")
    _assert_avatar_downloadable(resp, content, "守卫不影响正常下载")
