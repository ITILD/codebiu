from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from lancedb import connect_async, AsyncConnection, AsyncTable
    from lancedb.pydantic import LanceModel, Vector
from pydantic import BaseModel
from common.utils.db.do.db_config import LancedbConfig
from common.utils.db.session.interface.db_vector_interface import DBVectorInterface
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# class VectorBase(LanceModel):
#     """向量基类"""

#     vector: Vector(1024)


class DBVectorLancedb(DBVectorInterface):
    """
    LanceDB向量数据库实现
    封装向量数据库操作
    """

    database: str = None
    async_vector: AsyncConnection = None

    def __init__(self, lancedb_config: LancedbConfig):
        """
        初始化LanceDB向量数据库连接

        Args:
            lancedb_config: LanceDB数据库配置对象
        """
        self.database = Path(lancedb_config.database).resolve().as_posix()

    async def connect(self, log_bool=False):
        """
        建立数据库连接

        Args:
            log_bool: 是否启用日志
        """
        try:
            from lancedb import connect_async
            # 创建LanceDB客户端实例
            self.async_vector = await connect_async(self.database)

            if log_bool:
                logger.info(f"LanceDB数据库连接成功: {self.database}")
        except Exception as e:
            raise Exception(f"LanceDB数据库连接失败: {e}")

    async def create_table(
        self,
        schema_cls: type[BaseModel],
        vector_dims: dict[str, int] = {"vector": 1024},
    ) -> AsyncTable:
        """
        创建 LanceDB 表结构（空表）

        Args:
            schema_cls: 原始 Pydantic 模型类（BaseModel 子类）
            vector_dims: 向量字段名 -> 维度 的映射
        """
        try:
            table_name = schema_cls.__name__.lower()
            lance_model_cls = self._convert_to_lance_model(schema_cls, vector_dims)
            # 通过 schema= 传入模型类，data=None 表示空表
            async_table = await self.async_vector.create_table(
                table_name,
                data=None,  # 明确无初始数据
                schema=lance_model_cls,
                mode="overwrite",  # 覆盖,避免表已存在报错
            )
            return async_table

        except Exception as e:
            raise Exception(f"LanceDB创建表失败: {e}") from e

    def _convert_to_lance_model(
        self,
        schema_cls: type[BaseModel],
        vector_dims: dict[str, int] = {"vector": 1024},
    ) -> type[LanceModel]:
        """
        将 Pydantic BaseModel 类转换为 LanceModel 子类。
        向量字段使用 Vector(dim)，其他字段保留原注解。
        """
        from lancedb.pydantic import LanceModel,Vector
        annotations = {}
        for name, field in schema_cls.model_fields.items():
            if name in vector_dims:
                # 使用 Vector(dim) 表示向量字段
                annotations[name] = Vector(vector_dims[name])
            else:
                # 保留原始类型注解
                annotations[name] = field.annotation

        # 动态创建 LanceModel 子类
        return type(
            schema_cls.__name__,
            (LanceModel,),
            {
                "__annotations__": annotations,
                "__doc__": f"Lance model for {schema_cls.__name__}",
            },
        )

    async def add(
        self,
        data_list_class: list[BaseModel],
    ) -> None:
        """
        向 LanceDB 表中添加数据。

        Args:
            data_list_class: 要添加的数据列表
        """
        table_name = data_list_class[0].__class__.__name__.lower()
        async_table = await self.async_vector.open_table(table_name)
        data_list_dict = [item.model_dump() for item in data_list_class]
        await async_table.add(data_list_dict)

    async def search(
        self,
        schema_cls: type[BaseModel],
        query_vector: list[float],
        vector_dims_key: str = "vector",
    ) -> list[type[BaseModel]]:
        """
        查询 LanceDB 表中与查询向量最相似的记录。

        Args:
            schema_cls: 原始 Pydantic 模型类（BaseModel 子类）
            query_vector: 查询向量
        """
        table_name = schema_cls.__name__.lower()
        async_table = await self.async_vector.open_table(table_name)
        async_results = await async_table.search(query_vector)
        # 排除向量字段，只返回其他字段
        query_fields = [
            field
            for field in schema_cls.model_fields.keys()
            if field != vector_dims_key
        ]
        # query_fields.append('_distance')
        result_temp = await async_results.select(query_fields).to_list()

        result: list[type[BaseModel]] = [
            schema_cls.model_validate(item) for item in result_temp
        ]
        return result
