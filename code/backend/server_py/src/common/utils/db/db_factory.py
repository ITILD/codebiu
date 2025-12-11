from common.utils.db.do.db_config import (
    DBConfig,
    PostgresConfig,
    RedisConfig,
    MilvusConfig,
    Neo4jConfig,
)
from common.utils.db.session.impl.db_postgre import DBPostgre
from common.utils.db.session.impl.db_sqlite import DBSqlite
from common.utils.db.session.interface.db_relational_interface import (
    DBRelationInterface,
)
from common.utils.db.session.impl.db_cache_redis import DBCacheRedis
from common.utils.db.session.impl.db_cache_fakeredis import DBCacheFakeredis
from common.utils.db.session.interface.db_cache_interface import DBCacheInterface
from common.utils.db.session.interface.db_vector_interface import DBVectorInterface
from common.utils.db.session.interface.db_graph_interface import DBGraphInterface
from common.utils.db.session.impl.db_vector_milvus import DBVectorMilvus
from common.utils.db.session.impl.db_vector_milvus_lite import DBVectorMilvusLite
from common.utils.db.session.impl.db_graph_neo4j import DBGraphNeo4j
from common.utils.db.session.impl.db_graph_kuzu import DBGraphKuzu


class DBFactory:
    """
    根据参数创建多种数据库连接
    """

    @classmethod
    def create_rel(cls, db_config: DBConfig) -> DBRelationInterface:
        if isinstance(db_config, PostgresConfig):
            db_rel = DBPostgre(db_config)
        else:
            db_rel = DBSqlite(db_config)
        return db_rel

    # 缓存数据库连接
    @classmethod
    def create_cache(cls, db_config: DBConfig) -> DBCacheInterface:
        if isinstance(db_config, RedisConfig):
            db_cache = DBCacheRedis(db_config)
        else:
            db_cache = DBCacheFakeredis(db_config)
        return db_cache

    @classmethod
    def create_vector(cls, db_config: DBConfig) -> DBVectorInterface:
        if isinstance(db_config, MilvusConfig):
            db_vector = DBVectorMilvus(db_config)
        else:
            db_vector = DBVectorMilvusLite(db_config)
        return db_vector

    @classmethod
    def create_graph(cls, db_config: DBConfig) -> DBGraphInterface:
        if isinstance(
            db_config,
            Neo4jConfig,
        ):
            db_graph = DBGraphNeo4j(db_config)
        else:
            db_graph = DBGraphKuzu(db_config)
        return db_graph
