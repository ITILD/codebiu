from common.utils.db.do.db_config import DBConfig, PostgresConfig, RedisConfig
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
    def create_milvus(cls, db_config: DBConfig) -> DBVectorInterface:
        # from common.utils.db.session.impl.db_vector_milvus import DBVectorMilvus
        # return DBVectorMilvus(db_config)
        pass
    
    @classmethod
    def create_graph(cls, db_config: DBConfig) -> DBGraphInterface:
        # from common.utils.db.session.impl.db_graph_kuzu import DBGraphKuzu
        # return DBGraphKuzu(db_config)
        pass
