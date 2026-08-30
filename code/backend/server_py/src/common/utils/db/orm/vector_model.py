"""向量模型层(与具体向量数据库实现解耦)

类似 SQLModel 之于 sqlite/postgresql:
- VectorModel 是通用的向量表声明基类,不依赖任何具体向量库
- milvus/lancedb 等实现(session/impl/*)平级消费注册表,由 DBFactory 按配置选择
"""
from pydantic import BaseModel, Field
from typing import ClassVar
import logging

logger = logging.getLogger(__name__)


class VectorBase(BaseModel):
    """向量基类"""

    embedding: list[float] = Field(
        description="向量数据",
        vector_dim=1024,
    )
    content: str = Field(
        description="文本内容,用于BM25分析的文本",
        json_schema_extra={
            "max_length": 8192,
            "enable_analyzer": True,
            "analyzer_params": {"tokenizer": "icu"},  # ICU 会自动处理中英文混合
        },
    )


class VectorModel(VectorBase):
    """向量模型

    类似 SQLModel 的注册能力:
    - 子类通过 `table=True` 声明为向量库表,定义时自动注册到 registry
    - 由 db_vector.create_all() 统一创建所有已注册的表
    - 向量字段通过 Field 的 vector_dim 参数声明维度(如 Field(vector_dim=1024)),
      可通过 vector_dims() 提取

    用法:
        class MyChunk(VectorModel, table=True):
            id: str = Field(primary_key=True)
            embedding: list[float] = Field(vector_dim=1024)
    """

    # 向量表注册表(类似 SQLModel.metadata): 表名(类名小写) -> 模型类
    # 注: 命名避开 metadata,防止与DO模型的元数据字段撞名
    registry: ClassVar[dict[str, type["VectorModel"]]] = {}

    def __init_subclass__(cls, table: bool = False, **kwargs):
        super().__init_subclass__(**kwargs)
        if table:
            table_name = cls.__name__.lower()
            if table_name in VectorModel.registry:
                logger.warning(
                    f"向量表 {table_name} 重复注册, "
                    f"{VectorModel.registry[table_name]} 将被 {cls} 覆盖"
                )
            VectorModel.registry[table_name] = cls
            logger.debug(f"向量表 {table_name} 已注册: {cls}")

    @classmethod
    def vector_dims(cls) -> dict[str, int]:
        """提取所有声明了 vector_dim 的字段及其维度映射"""
        dims: dict[str, int] = {}
        for name, field_info in cls.model_fields.items():
            if isinstance(field_info.json_schema_extra, dict):
                dim = field_info.json_schema_extra.get("vector_dim")
                if isinstance(dim, int):
                    dims[name] = dim
        return dims
