import uuid
from sqlmodel import SQLModel, Field, Column

#
from common.utils.db.do.vector_pg import VectorPG


class VectorMixin(SQLModel):
    """向量混合类(通过类属性动态设置维度)"""

    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(VectorPG()),  # 默认1024维
        description="向量嵌入表示",
    )


class DocumentBase(SQLModel):
    __table_args__ = {"schema": "public"}
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    content: str = Field()


class Document(VectorMixin, DocumentBase, table=True):
    # index=True 索引
    pid: str = Field(default_factory=lambda: str(uuid.uuid4()), index=True)
    # 动态覆盖默认维度
    _VECTOR_DIM: int = 1024
    embedding: list[float] | None = Field(sa_column=Column(VectorPG(dim=_VECTOR_DIM)))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.embedding and len(self.embedding) != self._VECTOR_DIM:
            raise ValueError(f"向量维度必须为{self._VECTOR_DIM}")


class DocumentSelect(DocumentBase):
    similarity: float = Field(default=None)  # 相似度
