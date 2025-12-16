from lancedb import connect_async, AsyncConnection
from lancedb.pydantic import LanceModel, Vector
from pydantic import BaseModel
from common.utils.db.do.db_config import LancedbConfig
from common.utils.db.session.interface.db_vector_interface import DBVectorInterface
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# class VectorBase(LanceModel):
#     """向量基类"""

#     content_vec: Vector(1024)


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
            # 创建LanceDB客户端实例
            self.async_vector = await connect_async(self.database)

            if log_bool:
                logger.info(f"LanceDB数据库连接成功: {self.database}")
        except Exception as e:
            raise Exception(f"LanceDB数据库连接失败: {e}")

    async def create_table(
        self,
        schema_cls: type[BaseModel],
        vector_dims: dict[str, int] = {"content_vec": 1024}
    ) -> None:
        """
        创建 LanceDB 表结构（空表）
        
        Args:
            schema_cls: 原始 Pydantic 模型类（BaseModel 子类）
            vector_dims: 向量字段名 -> 维度 的映射
        """
        try:
            table_name = schema_cls.__name__.lower()
            lance_model_cls = self._convert_to_lance_model(schema_cls, vector_dims)
            # ✅ 关键：通过 schema= 传入模型类，data=None 表示空表
            await self.async_vector.create_table(
                table_name,
                data=None,        # 明确无初始数据
                schema=lance_model_cls,
                mode="overwrite"  # 可选：避免表已存在报错
            )
            
        except Exception as e:
            raise Exception(f"LanceDB创建表失败: {e}") from e

    def _convert_to_lance_model(self, schema_cls: type[BaseModel], vector_dims: dict[str, int]) -> type[LanceModel]:
        """
        将 Pydantic BaseModel 类转换为 LanceModel 子类。
        向量字段使用 Vector(dim)，其他字段保留原注解。
        """
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
            }
        )
