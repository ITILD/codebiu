"""数据库连接门面: 业务代码 `from common.config.db import DaoRel, db_vector` 用法完全不变。

关键设计:
- 导出对象身份恒定(代理), 实现按"调用时"从 runtime.db_manager 解析
  → 动态配置刷新/连接重建后, 存量 DAO/Service 无需任何改动
- 连接装配分段: start_rel()(yaml 引导, 先于动态配置) / start_from_settings()(动态配置)
- 修复原实现"import 期 start()"的副作用(测试/Celery worker/惰性启动的最大障碍)
"""
from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING

from common.runtime import AttrDict, runtime
from common.utils.db.db_factory import DBFactory
from common.utils.db.do.db_config import DBConfigFactory, DBConfig
from common.utils.db.session.interface.db_relational_interface import (
    DBRelationInterface,
)
from common.utils.db.session.interface.db_vector_interface import DBVectorInterface
from common.utils.db.session.interface.db_graph_interface import DBGraphInterface
from common.utils.db.session.interface.db_cache_interface import DBCacheInterface
from common.utils.db.utils.async_transactional import AsyncTransactional

#
from redis.asyncio import Redis

if TYPE_CHECKING:
    from pymilvus import AsyncMilvusClient
    from lancedb import AsyncConnection  # 仅类型检查时导入

import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库连接管理器: 分段装配(关系库=引导段; 缓存/向量/图=动态配置段)"""

    def __init__(self):
        self.db_rel: DBRelationInterface | None = None
        self.db_cache: DBCacheInterface | None = None
        # 向量库实现惰性创建: 首次访问 db_vector 属性时才加载 pymilvus/lancedb
        # (pymilvus 连带 pandas/pyarrow 约 150MB+, 避免 import 期占用)
        self._db_vector: DBVectorInterface | None = None
        self._db_vector_config: DBConfig | None = None
        self.db_graph: DBGraphInterface | None = None
        # 事务管理器(AsyncTransactional 实例, 经 call() 供 DaoRel 门面动态解析)
        self.DaoRel: AsyncTransactional | None = None
        # 异步缓存数据库连接
        self.async_cache: Redis | None = None
        # 异步向量数据库连接  注意只能异步连接  生命周期需要运行时获取
        self._async_vector: AsyncConnection | AsyncMilvusClient | None = None

    @property
    def async_vector(self) -> AsyncConnection | AsyncMilvusClient | None:
        """获取异步向量库连接(lancedb连接或milvus客户端)"""
        return self._async_vector

    @property
    def db_vector(self) -> DBVectorInterface | None:
        """获取向量库实现(惰性): 未配置返回 None; 已配置时首次访问才创建实例,
        此时才加载 pymilvus/lancedb 重量级 SDK(连接仍由 connect() 建立)"""
        if self._db_vector is None and self._db_vector_config is not None:
            self._db_vector = DBFactory.create_vector(self._db_vector_config)
        return self._db_vector

    def start_rel(self):
        """引导段: 关系型数据库(配置来自 yaml, 先于动态配置可用)"""
        from common.config.index import conf, is_dev

        if conf.db_rel.type:
            self.db_rel_config: DBConfig = DBConfigFactory.create(
                conf.db_rel.type, conf.db_rel
            )
            self.db_rel = DBFactory.create_rel(self.db_rel_config)
            self.db_rel.connect(is_dev)
            # 增强版异步事务管理器
            self.DaoRel = AsyncTransactional(self.db_rel.session_factory)

    async def create_sys_config_table(self):
        """提前创建 sys_config 表(init_runtime 中动态配置种子/读取先于全量建表)"""
        from common.config.dynamic.do import SysConfig

        async with self.db_rel.engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: SysConfig.__table__.create(sync_conn, checkfirst=True)
            )

    async def start_from_settings(self):
        """动态段: 缓存/向量/图数据库(配置来自 sys_config 动态配置)"""
        from common.config.dynamic import get_settings
        from common.config.dynamic.schemas import (
            DBCacheSettings,
            DBGraphSettings,
            DBVectorSettings,
        )

        cache = await get_settings(DBCacheSettings)
        if cache.type:
            self.db_cache = DBFactory.create_cache(
                DBConfigFactory.create(cache.type, _adapt(cache))
            )
            self.db_cache.connect()
            self.async_cache = self.db_cache.async_cache

        vector = await get_settings(DBVectorSettings)
        if vector.type:
            # 仅记录配置, 实现延迟到首次访问 db_vector 属性时创建(惰性加载 SDK)
            self._db_vector_config = DBConfigFactory.create(
                vector.type, _adapt(vector)
            )

        graph = await get_settings(DBGraphSettings)
        if graph.type:
            self.db_graph = DBFactory.create_graph(
                DBConfigFactory.create(graph.type, _adapt(graph))
            )
        logger.info(
            "动态段数据库装配完成: "
            f"cache={'on' if self.db_cache else 'off'} "
            f"vector={'on' if self._db_vector_config else 'off'} "
            f"graph={'on' if self.db_graph else 'off'}"
        )

    async def table_create_all(self):
        """创建所有关系表与向量表(向量库连接不存在时会先建立连接)"""
        # 创建所有数据库表
        if self.db_rel:
            await self.db_rel.create_all()
        # 创建所有向量表(VectorModel(table=True) 注册的表),向量库需先建立连接
        if self.db_vector:
            if self._async_vector is None:
                await self.db_vector.connect()
                self._async_vector = self.db_vector.async_vector
            await self.db_vector.create_all()

    async def connect_all(self):
        """特殊的连接"""
        # 向量数据库连接
        if self.db_vector:
            # table_create_all 可能已建立连接,避免重复连接
            if self._async_vector is None:
                await self.db_vector.connect()
                self._async_vector = self.db_vector.async_vector
            await self.db_vector.load_all()

    async def shutdown(self):
        """关闭资源"""
        pass


def _adapt(settings) -> AttrDict:
    """Pydantic 配置模型 → DBConfigFactory 兼容的属性风格 dict(剔除 None 字段)"""
    return AttrDict({k: v for k, v in settings.model_dump().items() if v is not None})


# 真实管理器单例(装配点经 manager() 获取; 业务代码一律走下方门面)
_manager = DatabaseManager()


def manager() -> DatabaseManager:
    """返回真实 DatabaseManager 实例(仅供 init_runtime 装配点使用; 业务代码勿用)"""
    return _manager


class _Facade:
    """恒定身份门面: 属性转发到 runtime.db_manager 的同名成员(调用时解析)"""

    __slots__ = ("_name",)

    def __init__(self, name: str):
        object.__setattr__(self, "_name", name)

    def _target(self):
        mgr = runtime.db_manager
        if mgr is None:
            raise RuntimeError(
                "runtime 未初始化: 请先 await init_runtime()(lifespan/worker/脚本装配点)"
            )
        name = object.__getattribute__(self, "_name")
        if name == "db_manager":  # 门面即管理器本身
            return mgr
        target = getattr(mgr, name)
        if target is None:
            raise RuntimeError(
                f"runtime.db_manager.{name} 未装配(对应数据库未启用?)"
            )
        return target

    def __getattr__(self, name):
        return getattr(self._target(), name)

    def __repr__(self) -> str:
        try:
            return repr(self._target())
        except RuntimeError:
            return f"<Facade {object.__getattribute__(self, '_name')} (未装配)>"


# 全局门面(身份恒定; from 导入拿到的永远是同一个代理对象)
db_manager = _Facade("db_manager")
db_rel = _Facade("db_rel")
db_cache = _Facade("db_cache")
async_cache = _Facade("async_cache")
db_vector = _Facade("db_vector")
db_graph = _Facade("db_graph")


class _DaoRelFacade:
    """@DaoRel 门面: 装饰返回 trampoline, 每次调用按当前 runtime 解析事务实现

    这样连接重建/动态刷新后, 已装饰的 DAO 方法自动使用新 session_factory。
    """

    def __call__(self, func):
        @wraps(func)
        async def trampoline(*args, **kwargs):
            impl = runtime.db_manager.DaoRel if runtime.db_manager else None
            if impl is None:
                raise RuntimeError(
                    "runtime 未初始化或关系库未启用, 无法执行 DAO 事务"
                )
            return await impl.call(func, *args, **kwargs)

        return trampoline


DaoRel = _DaoRelFacade()
