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
