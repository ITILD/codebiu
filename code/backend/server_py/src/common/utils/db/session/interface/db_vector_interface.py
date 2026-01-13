from abc import ABC, abstractmethod
from common.utils.db.do.db_config import DBConfig
from pydantic import BaseModel

class DBVectorInterface(ABC):
    """
    向量化数据库接口
    """

    def __init__(self, config: DBConfig) -> None:
        """
        初始化方法。

        子类必须实现此方法，通常用于接收数据库连接所需的配置参数
        (例如：主机地址、端口、用户名、密码、数据库名等)。
        """
        raise NotImplementedError("子类必须实现 __init__ 方法")
    def connect(self, log_bool=False):
        """
        建立数据库连接

        Args:
            log_bool: 是否启用日志
        """
        raise NotImplementedError("子类必须实现 connect 方法")
    
    async def create_table(
        self,
        schema_cls: type[BaseModel],
        vector_dims: dict[str, int] = {"vector": 1024},
    ):
        """
        创建表格

        Args:
            schema_cls: 表格的模型类
            vector_dims: 向量字段的维度，默认 {"vector": 1024}

        Returns:
            AsyncTable: 异步表格对象
        """
        raise NotImplementedError("子类必须实现 create_table 方法")

    async def add(
        self,
        schema_cls: type[BaseModel],
        data: dict,
    ):
        """
        添加数据

        Args:
            schema_cls: 表格的模型类
            data: 要添加的数据，字典格式

        Returns:
            None
        """
        raise NotImplementedError("子类必须实现 add 方法")
    
    async def search(
        self,
        schema_cls: type[BaseModel],
        query_vector: list[float],
        top_k: int = 5,
    ):
        """
        搜索向量

        Args:
            schema_cls: 表格的模型类
            query_vector: 查询向量，列表格式
            top_k: 返回的Top-K结果，默认5

        Returns:
            list[dict]: 搜索结果，每个元素为一个字典，包含数据和相似度
        """
        raise NotImplementedError("子类必须实现 search 方法")
