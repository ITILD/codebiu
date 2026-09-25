"""sys_config 动态配置接口测试(管理员鉴权链路 + 打码 + 更新回读)"""
import pytest

pytestmark = pytest.mark.asyncio


async def test_list_requires_auth(anon_client):
    """匿名访问配置列表 → 401"""
    resp = await anon_client.get("/sys-configs")
    assert resp.status_code == 401


async def test_list_forbidden_for_normal_user(user_client):
    """普通用户(未授权 main:config)访问 → 403

    自愈: 历史版本 default_policies 曾含 ("main","*","read") 通配策略,
    声明变更只做增量同步不回收, 此处显式清理该脏策略(幂等)。
    """
    from module_authorization.config.casbin_rule import auth_manager

    await auth_manager.enforcer.remove_filtered_policy(0, "user", "main", "*", "read")
    resp = await user_client.get("/sys-configs")
    assert resp.status_code == 403


async def test_list_groups(client):
    """管理员可列出全部配置组, 组元数据齐全"""
    resp = await client.get("/sys-configs")
    assert resp.status_code == 200
    groups = {g["group"]: g for g in resp.json()["groups"]}
    for name in (
        "token", "email", "websearch", "file_system",
        "db_cache", "db_vector", "db_graph", "tasks", "admin",
    ):
        assert name in groups
    assert groups["db_cache"]["restart_required"] is True
    assert groups["email"]["name"] == "邮箱服务"


async def test_get_unknown_group(client):
    """未知配置组查询 → 400"""
    resp = await client.get("/sys-configs/no_such")
    assert resp.status_code == 400


async def test_secret_masked(client):
    """密钥字段只回 has_value, 不回明文"""
    resp = await client.get("/sys-configs/token")
    assert resp.status_code == 200
    fields = {f["key"]: f for f in resp.json()["fields"]}
    assert fields["secret_key"]["type"] == "secret"
    assert fields["secret_key"]["value"] is None
    assert fields["secret_key"]["has_value"] is True
    assert fields["expire_minutes"]["value"] == 30


async def test_update_and_readback(client):
    """更新 websearch.max_results 后读回新值(即时生效), 测完恢复"""
    resp = await client.put("/sys-configs/websearch", json={"data": {"max_results": 25}})
    assert resp.status_code == 204
    resp = await client.get("/sys-configs/websearch")
    fields = {f["key"]: f for f in resp.json()["fields"]}
    assert fields["max_results"]["value"] == 25
    # 嵌套子组密钥字段(tavily.api_key)更新缺省时保持旧值: 仅回 has_value
    assert fields["tavily.api_key"]["has_value"] is True
    # 恢复默认, 避免污染其他用例
    await client.put("/sys-configs/websearch", json={"data": {"max_results": 10}})


async def test_secret_keep_on_absent(client):
    """密钥字段缺省提交 → 保持旧值(不误清空)"""
    resp = await client.put("/sys-configs/token", json={"data": {"expire_minutes": 45}})
    assert resp.status_code == 204
    resp = await client.get("/sys-configs/token")
    fields = {f["key"]: f for f in resp.json()["fields"]}
    assert fields["secret_key"]["has_value"] is True
    assert fields["expire_minutes"]["value"] == 45
    await client.put("/sys-configs/token", json={"data": {"expire_minutes": 30}})


async def test_tasks_update_invalidates_celery_app(client):
    """更新 tasks 组后 celery app 缓存失效(下次访问按新参数重建)"""
    from common.config import tasks as tasks_config

    old_app = tasks_config._celery_app
    resp = await client.put("/sys-configs/tasks", json={"data": {"engine": "local"}})
    assert resp.status_code == 204
    assert tasks_config._celery_app is None or tasks_config._celery_app is not old_app
    # 恢复(避免影响后续用例的引擎快照)
    await client.put("/sys-configs/tasks", json={"data": {"engine": "local"}})


async def test_update_unknown_group(client):
    """未知配置组更新 → 400"""
    resp = await client.put("/sys-configs/no_such", json={"data": {}})
    assert resp.status_code == 400


async def test_update_validation_error(client):
    """字段校验失败(extra=forbid / 类型不符)→ 400"""
    resp = await client.put("/sys-configs/websearch", json={"data": {"max_results": "abc"}})
    assert resp.status_code == 400
    resp = await client.put("/sys-configs/websearch", json={"data": {"not_a_field": 1}})
    assert resp.status_code == 400
