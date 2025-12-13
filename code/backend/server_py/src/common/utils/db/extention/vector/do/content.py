
from sqlmodel import SQLModel, Field, Column
from common.utils.db.extention.vector.colum.vector_pg import VectorPG
from common.utils.db.extention.vector.colum.vector_sqlite import VectorSqlite

class VectorMixinPG(SQLModel):
    """向量混合类(通过类属性动态设置维度)

    提供向量字段的基础定义，可被其他模型类继承使用
    """

    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(VectorPG()),  # 默认使用1024维度的向量类型
        description="存储文本的向量嵌入表示，用于相似度计算",
    )
class VectorMixinSqLite(SQLModel):
    """向量混合类(通过类属性动态设置维度)

    提供向量字段的基础定义，可被其他模型类继承使用
    """

    pass
    
