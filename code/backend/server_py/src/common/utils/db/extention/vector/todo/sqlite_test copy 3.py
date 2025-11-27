from sqlmodel import SQLModel, Field, Session, create_engine, select, col
from sqlalchemy import Column, func
from sqlalchemy.types import UserDefinedType
import numpy as np
import struct
import sqlite3
import sqlite_vec

# --- 辅助函数：序列化向量 ---
def serialize_f32(value: list[float] | np.ndarray) -> bytes:
    """将 float 列表转换为 LE 字节流 (Little Endian float32)"""
    if value is None:
        return b""
    # 确保是一维 float32 数组
    arr = np.asarray(value, dtype=np.float32).flatten()
    return struct.pack(f"{len(arr)}f", *arr)

# --- 核心：自定义向量类型 ---
class VectorSqlite(UserDefinedType):
    """SQLite sqlite-vec 向量类型"""
    cache_ok = True

    def __init__(self, dim: int | None = None):
        super().__init__()
        self.dim = dim

    def get_col_spec(self, **kw):
        return "BLOB"

    def bind_processor(self, dialect):
        def process(value):
            return serialize_f32(value)
        return process

    def result_processor(self, dialect, coltype):
        def process(value: bytes | None) -> np.ndarray | None:
            if value is None:
                return None
            return np.array(struct.unpack(f"{len(value)//4}f", value), dtype=np.float32)
        return process

    # --- 关键修改：定义比较器 ---
    class comparator_factory(UserDefinedType.Comparator):
        """
        这里定义了 .cosine() 和 .l2() 方法，
        SQLAlchemy 会将它们翻译成 sqlite-vec 的 SQL 函数。
        """
        def cosine(self, other):
            # 将 .cosine(vec) 转换为 SQL: vec_distance_cosine(column, serialized_vec)
            return func.vec_distance_cosine(self.expr, serialize_f32(other))

        def l2(self, other):
            # 将 .l2(vec) 转换为 SQL: vec_distance_l2(column, serialized_vec)
            return func.vec_distance_l2(self.expr, serialize_f32(other))

# --- 模型定义 ---
class VecItem(SQLModel, table=True):
    __tablename__ = "vec_items"
    id: int | None = Field(default=None, primary_key=True)
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column("embedding", VectorSqlite(dim=8))
    )
    content: str | None = Field(default=None)
    # 假设还有其他字段用于演示过滤
    ntype: str | None = Field(default="doc") 

# --- ORM 搜索函数 (完全复刻 pgvector 风格) ---
def search_with_orm(
    session: Session,
    search_vector: list[float],
    limit: int = 3,
    min_similarity: float = 0.0 # 0.0 表示不限制
):
    """
    使用 SQLModel/SQLAlchemy ORM 风格进行搜索。
    """
    
    # 1. 定义距离表达式 (Distance)
    # vec_distance_cosine 返回的是余弦距离 (0 到 2)
    distance_expr = VecItem.embedding.cosine(search_vector)
    
    # 2. 定义相似度表达式 (Similarity = 1 - Distance)
    similarity_expr = (1.0 - distance_expr).label("similarity")

    stmt = (
        select(
            VecItem,
            similarity_expr
        )
        # 3. 普通 SQL 过滤条件 (混合查询)
        .where(VecItem.ntype == "doc") 
        # 4. 向量相似度过滤 (例如: 相似度 > 0.5 等价于 距离 < 0.5)
        .where(distance_expr < (1.0 - min_similarity))
        # 5. 排序：距离越小越好 (即相似度越高越好)
        .order_by(distance_expr.asc())
        .limit(limit)
    )

    results = session.exec(stmt).all()
    
    # 格式化输出
    formatted_results = []
    for item, similarity in results:
        formatted_results.append({
            "item": item,
            "similarity": similarity,
            "distance": 1.0 - similarity
        })
    return formatted_results

# --- 运行测试 ---
if __name__ == "__main__":
    # 初始化
    conn = sqlite3.connect(":memory:")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn) # 加载插件
    conn.enable_load_extension(False)
    
    engine = create_engine("sqlite://", creator=lambda: conn)
    SQLModel.metadata.create_all(engine)

    # 插入数据
    data = [
        (1, [-0.200, 0.250, 0.341, -0.211, 0.645, 0.935, -0.316, -0.924], "item_1"),
        (2, [0.443, -0.501, 0.355, -0.771, 0.707, -0.708, -0.185, 0.362], "item_2"),
        (3, [0.716, -0.927, 0.134, 0.052, -0.669, 0.793, -0.634, -0.162], "item_3"),
        (4, [-0.710, 0.330, 0.656, 0.041, -0.990, 0.726, 0.385, -0.958], "item_4"),
    ]
    
    with Session(engine) as session:
        for i, vec, txt in data:
            session.add(VecItem(id=i, embedding=vec, content=txt, ntype="doc"))
        session.commit()

    # 执行 ORM 搜索
    query_vec = [-0.710, 0.330, 0.656, 0.041, -0.990, 0.726, 0.385, -0.958]
    
    print("=== ORM Search Results ===")
    results = search_with_orm(Session(engine), query_vec, limit=3)
    
    for r in results:
        print(f"ID: {r['item'].id}, Content: {r['item'].content}")
        print(f"Similarity: {r['similarity']:.4f}")
        print("-" * 20)