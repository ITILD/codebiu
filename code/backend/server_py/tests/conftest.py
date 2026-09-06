"""conftest.py pytest 默认测试配置文件
所有同目录测试文件运行前都会执行 conftest.py，不需要 import 导入。

基础设施:
- _app_lifespan: session 级触发完整 lifespan(建表/casbin/默认管理员引导),测试完关闭连接
- admin_headers: 管理员真实登录,返回 Bearer 鉴权头(走完整 JWT+casbin 链路)
- client: 带管理员鉴权的 httpx 异步客户端(ASGITransport 直连 app,无需启动服务器)
- anon_client: 匿名客户端(测登录/注册/401 场景)

约定:
- asyncio 默认 session loop(lifespan 与测试同 loop,asyncpg 连接池不跨 loop)
- 测试数据一律带时间戳唯一后缀,测完清理,不依赖执行顺序
"""

import logging
import sys
import time
import uuid

from httpx import ASGITransport, AsyncClient
import pytest_asyncio

# Windows 下切换 Selector 事件循环(psycopg 异步模式不支持 ProactorEventLoop,
# 必须在 pytest-asyncio 创建 session loop 之前设置策略)
if sys.platform == "win32":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from common.config.path import DIR_LOG
from common.config.index import is_dev
from common.utils.log.logging_rich import LoggingRich

# ==================== 日志 ====================
dev_log = LoggingRich(DIR_LOG, is_dev)
dev_log.setup()
logger = logging.getLogger(__name__)
logger.info("test log is set up ok")
logger.info("运行环境: %s", "测试 (tests)")

BASE_URL = "http://test"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _app_lifespan():
    """session 级: 触发完整 lifespan(连接池/建表/casbin/管理员引导),结束后关闭"""
    from app import app

    async with app.router.lifespan_context(app):
        logger.info("app lifespan started (tables/casbin/admin ready)")
        yield
    logger.info("app lifespan closed")


def _make_client(headers: dict | None = None) -> AsyncClient:
    """构造 ASGI 直连客户端(每次请求独立,避免状态串扰)"""
    from app import app

    return AsyncClient(
        transport=ASGITransport(app=app), base_url=BASE_URL, headers=headers or {}
    )


@pytest_asyncio.fixture(scope="session")
async def admin_token() -> str:
    """管理员登录获取访问令牌(走真实登录链路)"""
    async with _make_client() as ac:
        resp = await ac.post(
            "/authorization/auth/login",
            data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        )
    assert resp.status_code == 200, f"管理员登录失败: {resp.status_code} {resp.text}"
    return resp.json()["tokens"]["access"]["token"]


@pytest_asyncio.fixture(scope="session")
async def admin_headers(admin_token: str) -> dict:
    """带管理员 Bearer 鉴权头的请求头"""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest_asyncio.fixture(scope="session")
async def normal_user() -> dict:
    """注册一个普通(非管理员)用户, 返回 {username, headers}(测权限收紧/脱敏场景)"""
    suffix = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    username = f"u_{suffix}"
    password = "Test123456"
    async with _make_client() as ac:
        resp = await ac.post(
            "/authorization/auth/register",
            json={"username": username, "password": password, "nickname": "测试普通用户"},
        )
    assert resp.status_code == 200, f"普通用户注册失败: {resp.status_code} {resp.text}"
    token = resp.json()["tokens"]["access"]["token"]
    return {"username": username, "headers": {"Authorization": f"Bearer {token}"}}


@pytest_asyncio.fixture
async def user_client(normal_user: dict) -> AsyncClient:
    """带普通用户鉴权的异步测试客户端(非管理员, 每用例独立实例)"""
    async with _make_client(normal_user["headers"]) as ac:
        yield ac


@pytest_asyncio.fixture
async def client(admin_headers: dict) -> AsyncClient:
    """带管理员鉴权的异步测试客户端(每用例独立实例)"""
    async with _make_client(admin_headers) as ac:
        yield ac


@pytest_asyncio.fixture
async def anon_client() -> AsyncClient:
    """匿名客户端(无鉴权头,测公开端点/401 场景)"""
    async with _make_client() as ac:
        yield ac
