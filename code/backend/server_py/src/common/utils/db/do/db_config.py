from pydantic import BaseModel, Field, field_validator

_DB_REGISTRY: dict[str, type["DBConfig"]] = {}
class DBConfig(BaseModel):
    database: str = Field(..., description="数据库名/持久化地址")

    def __init_subclass__(cls, config_type: str | None = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if config_type is not None:
            _DB_REGISTRY[config_type] = cls
            
# 模型配置对象
class PostgresConfig(DBConfig, config_type="postgres"):
    host: str = Field(..., description="数据库地址")
    port: int = Field(..., description="数据库端口")
    user: str = Field(..., description="数据库用户名")
    password: str = Field(..., description="数据库密码")


class SqliteConfig(DBConfig, config_type="sqlite"):
    pass


class RedisConfig(DBConfig, config_type="redis"):
    db: int = Field(0, description="数据库索引")
    host: str = Field(..., description="数据库地址")
    port: int = Field(..., description="数据库端口")
    password: str | None = Field(None, description="数据库密码")


class FakeredisConfig(DBConfig, config_type="fakeredis"):
    pass


class MilvusConfig(DBConfig, config_type="milvus"):
    uri: str | None = Field(None, description="数据库地址")
    host: str | None = Field(None, description="数据库地址")
    port: int | None = Field(None, description="数据库端口")
    user: str | None = Field(None, description="数据库用户名")
    password: str | None = Field(None, description="数据库密码")
    token: str | None = Field(None, description="数据库token")


class LancedbConfig(DBConfig, config_type="lancedb"):
    pass


class GraphLocalConfig(DBConfig, config_type="graph_local"):
    pass


class Neo4jConfig(DBConfig, config_type="neo4j"):
    host: str = Field(..., description="数据库地址")
    port: int = Field(..., description="数据库端口")
    user: str = Field(..., description="数据库用户名")
    password: str = Field(..., description="数据库密码")


class DBEX:
    @staticmethod
    def get_config(type_: str, config_dict: dict) -> DBConfig:
        """
        根据 type_ 自动选择并实例化对应的配置模型
        """
        config_cls = _DB_REGISTRY.get(type_)
        if config_cls is None:
            raise ValueError(f"未知的数据库类型: {type_}. 支持的类型: {list(_DB_REGISTRY.keys())}")
        return config_cls.model_validate(config_dict)