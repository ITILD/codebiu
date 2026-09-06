# -*- coding: utf-8 -*-
"""module_ai/model_config 接口标准测试
挂在 /ai/model-configs,覆盖: 创建→分页列表→滚动列表→单个获取→更新→删除 全流程
以及参数校验(422)与不存在资源(404)分支
"""

import time
import uuid

import httpx

BASE = "/ai/model-configs"


def _make_config() -> dict:
    """构造唯一测试模型配置数据(时间戳+uuid 后缀,不依赖执行顺序)"""
    suffix = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    return {
        "model_type": "chat",
        "server_type": "openai",
        "model": f"test_model_{suffix}",
        "api_key": "test-key-not-real",
        "pay_in": 0.0,
        "pay_out": 0.0,
        "input_tokens": 8192,
        "out_tokens": 8192,
        "temperature": 0.7,
        "timeout": 60,
        "no_think": False,
    }


async def test_model_config_crud_flow(client: httpx.AsyncClient):
    """创建→单个获取→分页列表→滚动列表→更新→删除 全流程(try/finally 保证清理)"""
    data = _make_config()
    config_id: str | None = None
    deleted_id: str | None = None
    try:
        # 创建(201, 响应体为ID字符串)
        resp = await client.post(BASE, json=data)
        assert resp.status_code == 201, resp.text
        config_id = resp.json()
        assert isinstance(config_id, str) and config_id, f"创建应返回ID字符串: {config_id}"

        # 单个获取: 字段与创建数据一致
        resp = await client.get(f"{BASE}/{config_id}")
        assert resp.status_code == 200, resp.text
        got = resp.json()
        assert got["model"] == data["model"], "模型标识应与创建数据一致"
        assert got["model_type"] == "chat", "模型类型应与创建数据一致"
        assert got["user_id"], "配置应归属当前登录用户"
        # 未提供 url 时按 server_type 自动填充默认值
        assert got["url"] == "https://api.openai.com/v1", "openai 方案应自动填充默认URL"

        # 分页列表: 按唯一模型标识模糊过滤,应包含新建配置
        resp = await client.get(
            f"{BASE}/list",
            params={"page": 1, "size": 10, "model": data["model"]},
        )
        assert resp.status_code == 200, resp.text
        page = resp.json()
        assert page["total"] >= 1, "过滤后的分页列表应包含新建配置"
        assert any(item["id"] == config_id for item in page["items"]), "列表条目应包含新建配置"

        # 滚动列表: 应返回滚动分页结构
        resp = await client.get(f"{BASE}/scroll", params={"limit": 10, "direction": "up"})
        assert resp.status_code == 200, resp.text
        scroll = resp.json()
        assert isinstance(scroll["items"], list), "滚动列表应返回条目数组"
        assert "has_more" in scroll and "last_id" in scroll, "应返回滚动游标结构"

        # 更新(204)
        resp = await client.put(
            f"{BASE}/{config_id}", json={"temperature": 0.9, "no_think": True}
        )
        assert resp.status_code in (200, 204), resp.text

        # 验证更新生效
        resp = await client.get(f"{BASE}/{config_id}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["temperature"] == 0.9, "温度系数应已更新"
        assert resp.json()["no_think"] is True, "no_think 应已更新"

        # 删除(204)
        resp = await client.delete(f"{BASE}/{config_id}")
        assert resp.status_code in (200, 204), resp.text
        deleted_id = config_id
        config_id = None  # 已删除,finally 不再重复清理
    finally:
        # 兜底清理测试数据(已删除则忽略404)
        if config_id:
            resp = await client.delete(f"{BASE}/{config_id}")
            assert resp.status_code in (200, 204, 404), resp.text

    # 删除后再获取应 404
    assert deleted_id, "流程应已记录已删除的配置ID"
    resp = await client.get(f"{BASE}/{deleted_id}")
    assert resp.status_code == 404, resp.text


async def test_model_config_get_not_found(client: httpx.AsyncClient):
    """获取不存在的模型配置应 404"""
    resp = await client.get(f"{BASE}/nonexistent-config-{int(time.time() * 1000)}")
    assert resp.status_code == 404, resp.text


async def test_model_config_create_validation(client: httpx.AsyncClient):
    """创建参数校验: 缺少必填字段/非法枚举值应 422"""
    # 缺少必填的 model 字段
    resp = await client.post(BASE, json={"model_type": "chat", "server_type": "openai"})
    assert resp.status_code == 422, resp.text

    # 非法 server_type 枚举
    resp = await client.post(
        BASE,
        json={"model": f"test_model_{int(time.time() * 1000)}", "server_type": "not_a_server"},
    )
    assert resp.status_code == 422, resp.text

    # 非法 model_type 枚举
    resp = await client.post(
        BASE,
        json={"model": f"test_model_{int(time.time() * 1000)}", "model_type": "no_such_type"},
    )
    assert resp.status_code == 422, resp.text


async def test_model_config_default_params(client: httpx.AsyncClient):
    """获取模型默认参数应返回 kv 字典(服务层 pass 存根与 404 包装缺陷已修复)"""
    resp = await client.get(f"{BASE}/default-params/qwen-test-{int(time.time() * 1000)}")
    assert resp.status_code == 200, resp.text
    params = resp.json()["params"]
    assert params.get("temperature") == 0.7, f"默认温度应为 0.7: {params}"
    assert params.get("timeout") == 60, f"默认超时应为 60: {params}"


async def test_public_model_permission_and_masking(client: httpx.AsyncClient, user_client: httpx.AsyncClient):
    """公共模型权限与脱敏: 管理员创建公共模型后,
    非管理员可见但 url/api_key 被脱敏且不可修改/删除(403), 管理员可正常修改"""
    data = _make_config()
    data["scope"] = "public"
    model_id: str | None = None
    try:
        resp = await client.post(BASE, json=data)
        assert resp.status_code == 201, resp.text
        model_id = resp.json()

        # 非管理员单个获取: url/api_key 脱敏
        resp = await user_client.get(f"{BASE}/{model_id}")
        assert resp.status_code == 200, resp.text
        got = resp.json()
        assert got["url"] is None and got["api_key"] is None, f"非管理员查看公共模型应脱敏: {got}"

        # 非管理员列表: 同样脱敏
        resp = await user_client.get(f"{BASE}/list", params={"page": 1, "size": 10, "model": data["model"]})
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        target = next((i for i in items if i["id"] == model_id), None)
        assert target is not None, "公共模型应出现在普通用户可见列表中"
        assert target["url"] is None and target["api_key"] is None, "列表中公共模型应脱敏"

        # 非管理员修改/删除公共模型 → 403
        resp = await user_client.put(f"{BASE}/{model_id}", json={"temperature": 0.1})
        assert resp.status_code == 403, f"非管理员修改公共模型应 403: {resp.text}"
        resp = await user_client.delete(f"{BASE}/{model_id}")
        assert resp.status_code == 403, f"非管理员删除公共模型应 403: {resp.text}"

        # 管理员查看不脱敏、修改放行
        resp = await client.get(f"{BASE}/{model_id}")
        assert resp.status_code == 200, resp.text
        got = resp.json()
        assert got["url"] == "https://api.openai.com/v1", "管理员应看到明文 url"
        assert got["api_key"] == "test-key-not-real", "管理员应看到明文 api_key"
        resp = await client.put(f"{BASE}/{model_id}", json={"temperature": 0.8})
        assert resp.status_code in (200, 204), resp.text
    finally:
        if model_id:
            resp = await client.delete(f"{BASE}/{model_id}")
            assert resp.status_code in (200, 204, 404), resp.text


async def test_owner_filter_and_self_manage(client: httpx.AsyncClient, user_client: httpx.AsyncClient, normal_user: dict):
    """自建模型管理权: 普通用户可修改/删除自己的模型(明文可见);
    管理员可按所有者用户名过滤检索所有人的模型"""
    data = _make_config()
    model_id: str | None = None
    try:
        # 普通用户创建自己的模型
        resp = await user_client.post(BASE, json=data)
        assert resp.status_code == 201, resp.text
        model_id = resp.json()

        # 本人查看: 不脱敏
        resp = await user_client.get(f"{BASE}/{model_id}")
        assert resp.status_code == 200, resp.text
        got = resp.json()
        assert got["url"] == "https://api.openai.com/v1", "本人查看自建模型应看到明文 url"
        assert got["api_key"] == "test-key-not-real", "本人查看自建模型应看到明文 api_key"

        # 本人修改/删除放行(204)
        resp = await user_client.put(f"{BASE}/{model_id}", json={"temperature": 0.5})
        assert resp.status_code in (200, 204), resp.text

        # 管理员按所有者用户名过滤: 应能检索到该模型(管理员可见所有人模型)
        resp = await client.get(
            f"{BASE}/list",
            params={"page": 1, "size": 10, "model": data["model"], "user": normal_user["username"]},
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert any(i["id"] == model_id for i in items), "管理员按所有者过滤应检索到该模型"

        # 管理员按不存在的用户名过滤 → 空结果
        resp = await client.get(
            f"{BASE}/list",
            params={"page": 1, "size": 10, "model": data["model"], "user": f"no_such_user_{int(time.time() * 1000)}"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["total"] == 0, "不存在的所有者应返回空结果"

        # 普通用户删除自己的模型 → 204
        resp = await user_client.delete(f"{BASE}/{model_id}")
        assert resp.status_code in (200, 204), resp.text
        model_id = None
    finally:
        if model_id:
            resp = await client.delete(f"{BASE}/{model_id}")
            assert resp.status_code in (200, 204, 404), resp.text


async def test_seed_default_models_hook():
    """启动 seed 钩子幂等: 再次执行 ensure_default_models 不报错,
    且配置启用的类型(chat)存在生效的公共默认模型"""
    from module_ai.config.server import ensure_default_models
    from module_ai.dao.model_config import ModelConfigDao
    from module_ai.do.model_config import ModelScope

    # lifespan 已执行过一次, 此处再次执行验证幂等
    await ensure_default_models()

    cfg = await ModelConfigDao().get_default_by_type("chat", active_only=True)
    if cfg is None:
        # 环境未启用 chat 默认模型配置时跳过(不视为失败)
        return
    assert cfg.scope == ModelScope.PUBLIC, "seed 模型应为公共范围"
    assert cfg.is_default is True, "seed 模型应为默认公共模型"
    assert cfg.is_active is True, "seed 启用配置下模型应为生效状态"
