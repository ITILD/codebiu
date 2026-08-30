"""
langgraph AsyncPostgresSaver checkpointer 配置(模块级单例)

- 使用 psycopg AsyncConnectionPool 连接 PostgreSQL
- 连接池配置 autocommit=True(setup 的 CREATE INDEX CONCURRENTLY 需要在事务块外运行)
- setup() 创建 checkpointer 所需的表和索引
- 通过 asyncio.Lock 防止并发初始化竞态
"""
import asyncio
import logging
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from common.config.index import conf

logger = logging.getLogger(__name__)

_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None
_init_lock = asyncio.Lock()


def _build_pg_conn_string() -> str:
    """从配置构建 postgres 连接字符串(psycopg 格式，不含 +asyncpg)"""
    db = conf.db_rel
    return f"postgresql://{db.user}:{db.password}@{db.host}:{db.port}/{db.database}"


async def _configure_conn(conn) -> None:
    """连接池配置回调：设置 autocommit

    setup() 内的 CREATE INDEX CONCURRENTLY 要求在事务块外运行，
    因此每个连接创建后立即开启 autocommit。

    注意：异步连接的 autocommit 属性只读，必须使用 set_autocommit()。
    """
    await conn.set_autocommit(True)


async def get_checkpointer() -> AsyncPostgresSaver:
    """
    获取 AsyncPostgresSaver 单例

    首次调用时：
    1. 创建 AsyncConnectionPool(configure=_configure_conn, open=False)
    2. 打开连接池
    3. 创建 AsyncPostgresSaver 并执行 setup() 建表

    后续调用直接返回已创建的实例。
    通过 asyncio.Lock 防止并发请求重复初始化。
    """
    global _pool, _checkpointer

    if _checkpointer is not None:
        return _checkpointer

    async with _init_lock:
        # 防止其他协程初始化
        if _checkpointer is not None:
            return _checkpointer

        conn_string = _build_pg_conn_string()
        logger.info("正在初始化 AsyncPostgresSaver checkpointer...")

        # configure 作为构造参数传入，确保连接创建时即开启 autocommit
        pool = AsyncConnectionPool(
            conninfo=conn_string,
            open=False,
            configure=_configure_conn,
        )
        try:
            await pool.open()
            saver = AsyncPostgresSaver(pool)
            await saver.setup()
        except BaseException as e:
            await pool.close()   # 失败时回收
            raise e

        _pool = pool             # 全部成功后才写入全局
        _checkpointer = saver
        logger.info("AsyncPostgresSaver checkpointer 初始化完成")
        return _checkpointer


async def close_checkpointer() -> None:
    """关闭 checkpointer 和连接池(应用关闭时调用)"""
    global _pool, _checkpointer
    if _pool is not None:
        await _pool.close()
        _pool = None
        _checkpointer = None
        logger.info("AsyncPostgresSaver checkpointer 已关闭")
