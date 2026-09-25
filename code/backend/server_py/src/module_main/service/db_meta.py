"""数据库元信息只读服务:统一统计关系库/向量库/缓存/图数据库的运行信息

供数据监测页(/db/tables、/db/vector、/db/cache、/db/graph)消费,
只做元数据与计数的读取,不写入任何数据。
"""
from datetime import datetime

from sqlalchemy import text
from sqlmodel import SQLModel

from common.runtime import runtime
from common.utils.db.orm.vector_model import VectorModel

import logging

logger = logging.getLogger(__name__)


def _real():
    """取真实 DatabaseManager(runtime 未装配/未启用成员时为 None)

    状态展示类接口不能走 db.py 门面(代理恒真值), 须按真实装配情况返回"未启用"。
    """
    return runtime.db_manager


class DbMetaService:
    """数据库元信息统计服务(只读)"""

    # ############################### 关系数据库 ###############################
    @staticmethod
    async def tables(keyword: str | None = None) -> list[dict]:
        """
        列出关系库全部数据表及数据量/最近更新时间

        Args:
            keyword: 按表名/注释关键字过滤(不区分大小写)

        Returns:
            list[dict]: name/comment/column_count/row_count/last_updated
        """
        mgr = _real()
        rel = mgr.db_rel if mgr else None
        if rel is None or rel.engine is None:
            return []
        rows: list[dict] = []
        async with rel.engine.connect() as conn:
            # 按方言引用表名/列名(sqlite/postgres 双引号, mysql 反引号)
            preparer = conn.dialect.identifier_preparer
            for name, table in SQLModel.metadata.tables.items():
                comment = table.comment
                if keyword and keyword.lower() not in f"{name} {comment or ''}".lower():
                    continue
                quoted = preparer.quote(name)
                row_count = None
                last_updated = None
                # 数据条数(表尚未建表时跳过统计)
                try:
                    row_count = (
                        await conn.execute(text(f"SELECT COUNT(*) FROM {quoted}"))
                    ).scalar()
                except Exception:
                    pass
                # 最近更新时间(模型声明 updated_at 字段时才统计)
                if "updated_at" in table.columns:
                    try:
                        value = (
                            await conn.execute(
                                text(
                                    f"SELECT MAX({preparer.quote('updated_at')}) FROM {quoted}"
                                )
                            )
                        ).scalar()
                        if isinstance(value, datetime):
                            last_updated = value.isoformat()
                        else:
                            last_updated = value
                    except Exception:
                        pass
                rows.append(
                    {
                        "name": name,
                        "comment": comment,
                        "column_count": len(table.columns),
                        "row_count": row_count or 0,
                        "last_updated": last_updated,
                    }
                )
        return rows

    # ############################### 向量数据库 ###############################
    @staticmethod
    async def vector_tables() -> dict:
        """
        向量库表清单(表名/字段数/向量维度/数据条数)

        Returns:
            dict: {type, tables: [{name, field_count, vector_dims, row_count}]}
        """
        # 向量库实现经 runtime 真实解析(门面恒真值不适用于状态展示)
        mgr = _real()
        vec = mgr.db_vector if mgr else None
        if vec is None:
            return {"type": None, "tables": []}
        # 向量库连接生命周期在运行时获取,此处懒建立
        conn = mgr.async_vector
        if conn is None:
            await vec.connect()
            conn = vec.async_vector
        # VectorModel 注册表提供字段数/向量维度元信息
        registry = VectorModel.registry
        try:
            # milvus 客户端与 lancedb 连接均有 list_collections 方法
            names = list(await conn.list_collections())
        except Exception as e:
            logger.warning(f"获取向量库表名失败,回退到注册表: {e}")
            names = list(registry.keys())
        tables: list[dict] = []
        for name in names:
            model = registry.get(name)
            field_count = len(model.model_fields) if model else None
            dims = (
                "/".join(str(v) for v in model.vector_dims().values()) if model else None
            )
            row_count = None
            try:
                if hasattr(conn, "get_collection_stats"):
                    stats = await conn.get_collection_stats(name)
                    row_count = int(stats.get("num_entities") or 0)
                else:
                    table = await conn.open_table(name)
                    row_count = await table.count_rows()
            except Exception as e:
                logger.warning(f"统计向量表 {name} 数据量失败: {e}")
            tables.append(
                {
                    "name": name,
                    "field_count": field_count,
                    "vector_dims": dims,
                    "row_count": row_count,
                }
            )
        return {"type": type(vec).__name__, "tables": tables}

    # ############################### 缓存数据库(Redis) ###############################
    @staticmethod
    async def cache_info() -> dict:
        """
        Redis 缓存运行信息(键数量/内存/命中率/版本等)

        Returns:
            dict: 缓存概要信息,未启用时 type 为 None
        """
        mgr = _real()
        cache = mgr.db_cache if mgr else None
        ac = mgr.async_cache if mgr else None
        if ac is None:
            return {"type": None}
        cache_type = type(cache).__name__ if cache else None
        try:
            info = await ac.info()
            dbsize = await ac.dbsize()
        except Exception as e:
            return {"type": cache_type, "error": str(e)}
        hits = info.get("keyspace_hits") or 0
        misses = info.get("keyspace_misses") or 0
        total = hits + misses
        return {
            "type": cache_type,
            "dbsize": dbsize,
            "redis_version": info.get("redis_version"),
            "used_memory_human": info.get("used_memory_human"),
            "maxmemory_human": info.get("maxmemory_human"),
            "connected_clients": info.get("connected_clients"),
            "uptime_in_days": info.get("uptime_in_days"),
            "keyspace_hits": hits,
            "keyspace_misses": misses,
            "hit_rate": round(hits / total * 100, 2) if total else None,
        }

    # ############################### 图数据库 ###############################
    @staticmethod
    async def graph_info() -> dict:
        """
        图数据库运行信息(类型/连接状态/地址等,由各实现自述)

        Returns:
            dict: 图库信息,未启用时 type 为 None
        """
        mgr = _real()
        graph = mgr.db_graph if mgr else None
        if graph is None:
            return {"type": None}
        try:
            return await graph.get_info()
        except Exception as e:
            return {"type": type(graph).__name__, "error": str(e)}
