from pydantic import BaseModel, Field, field_validator


# 模型配置对象
class DBConfig(BaseModel):
    database: str = Field(..., description="数据库名/持久化地址")
    # charset: str = Field("utf8mb4", description="数据库字符集")
class PostgresConfig(DBConfig):
    """Postgres数据库配置"""
    host: str = Field(..., description="数据库地址")
    port: int = Field(..., description="数据库端口")
    user: str = Field(..., description="数据库用户名")
    password: str = Field(..., description="数据库密码")

class Neo4jConfig(DBConfig):
    """Postgres数据库配置"""
    host: str = Field(..., description="数据库地址")
    port: int = Field(..., description="数据库端口")
    user: str = Field(..., description="数据库用户名")
    password: str = Field(..., description="数据库密码")


class SqliteConfig(DBConfig):
    """Sqlite数据库配置"""
    pass
    
class KuzuConfig(DBConfig):
    """Kuzu数据库配置"""
    pass

class RedisConfig(DBConfig):
    """Redis数据库配置"""
    db: int = Field(0, description="数据库索引")
    host: str = Field(..., description="数据库地址")
    port: int = Field(..., description="数据库端口")

class FakeredisConfig(DBConfig):
    """Fakeredis数据库配置"""
    pass

class MilvusConfig(DBConfig):
    """Milvus数据库配置"""
    host: str = Field(..., description="数据库地址")
    port: int = Field(..., description="数据库端口")
    user: str = Field(..., description="数据库用户名")
    password: str = Field(..., description="数据库密码")
    database: str = Field(..., description="数据库名/持久化地址")
    collection_name: str = Field(..., description="集合名")
    
class MilvusLiteConfig(DBConfig):
    """Milvus Lite数据库配置"""
    database: str = Field(..., description="数据库名/持久化地址")
    collection_name: str = Field(..., description="集合名")
    
class DBEX:
    def get_config(type: str,config_dict)->DBConfig:
        if  type == "postgres":
            return PostgresConfig.model_validate(config_dict)
        elif  type == "sqlite":
            return SqliteConfig.model_validate(config_dict)
        # db_cache
        elif  type == "redis":
            return RedisConfig.model_validate(config_dict)
        elif  type == "fakeredis":
            return FakeredisConfig.model_validate(config_dict)
        # db_graph
        elif  type == "kuzu":
            return KuzuConfig.model_validate(config_dict)
        # db_vector
        elif  type == "milvus":
            return MilvusConfig.model_validate(config_dict)
        elif  type == "milvus_lite":
            return MilvusLiteConfig.model_validate(config_dict)
        else:
            raise ValueError(f"get_config 未知模型类型:{type}")
    