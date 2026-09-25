from common.utils.db.do.db_config import (
    DBConfig,
    PostgresConfig,
    RedisConfig,
    MilvusConfig,
    Neo4jConfig,
)
from common.utils.db.session.interface.db_relational_interface import (
    DBRelationInterface,
)
from common.utils.db.session.interface.db_cache_interface import DBCacheInterface
from common.utils.db.session.interface.db_vector_interface import DBVectorInterface
from common.utils.db.session.interface.db_graph_interface import DBGraphInterface


class DBFactory:
    """根据参数创建多种数据库连接

    各实现类延迟导入: 未启用的后端(如 neo4j/milvus/lancedb)不会在启动时加载
    其重量级 SDK(pymilvus 额外连带 pandas/pyarrow, 约省 150MB+)
    """

    @classmethod
    def create_rel(cls, db_config: DBConfig) -> DBRelationInterface:
        if isinstance(db_config, PostgresConfig):
            from common.utils.db.session.impl.db_postgre import DBPostgre

            db_rel = DBPostgre(db_config)
        else:
            from common.utils.db.session.impl.db_sqlite import DBSqlite

            db_rel = DBSqlite(db_config)
        return db_rel

    # 缓存数据库连接
    @classmethod
    def create_cache(cls, db_config: DBConfig) -> DBCacheInterface:
        if isinstance(db_config, RedisConfig):
            from common.utils.db.session.impl.db_cache_redis import DBCacheRedis

            db_cache = DBCacheRedis(db_config)
        else:
            from common.utils.db.session.impl.db_cache_fakeredis import DBCacheFakeredis

            db_cache = DBCacheFakeredis(db_config)
        return db_cache

    @classmethod
    def create_vector(cls, db_config: DBConfig) -> DBVectorInterface:
        if isinstance(db_config, MilvusConfig):
            from common.utils.db.session.impl.db_vector_milvus import DBVectorMilvus

            db_vector = DBVectorMilvus(db_config)
        else:
            from common.utils.db.session.impl.db_vector_lancedb import DBVectorLancedb

            db_vector = DBVectorLancedb(db_config)
        return db_vector

    @classmethod
    def create_graph(cls, db_config: DBConfig) -> DBGraphInterface:
        if isinstance(
            db_config,
            Neo4jConfig,
        ):
            from common.utils.db.session.impl.db_graph_neo4j import DBGraphNeo4j

            db_graph = DBGraphNeo4j(db_config)
        else:
            from common.utils.db.session.impl.db_graph_local import DBGraphLocal

            db_graph = DBGraphLocal(db_config)
        return db_graph
