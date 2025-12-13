from sqlmodel import SQLModel, Field, Session, create_engine, select
from sqlalchemy import Column, text, func
from sqlalchemy.dialects.sqlite.base import ischema_names
from sqlalchemy.types import UserDefinedType, Float
import numpy as np
import struct
import sqlite3
import sqlite_vec  # 必须安装 sqlite-vec

class VectorSqlite(UserDefinedType):
    """SQLite sqlite-vec 向量类型 - 使用 BLOB 存储，MATCH 查询"""
    cache_ok = True

    def __init__(self, dim: int | None = None):
        super().__init__()
        self.dim = dim

    def get_col_spec(self, **kw):
        # sqlite-vec 虚拟表中 embedding 列实际是 BLOB，但这里仅用于类型标注
        return "BLOB"

    def bind_processor(self, dialect):
        return self._to_blob

    def result_processor(self, dialect, coltype):
        def process(value: bytes | None) -> np.ndarray | None:
            if value is None:
                return None
            return np.array(struct.unpack(f"{len(value)//4}f", value), dtype=np.float32)
        return process

    def _to_blob(self, value) -> bytes | None:
        if value is None:
            return None
        arr = np.asarray(value, dtype=np.float32).flatten()
        if self.dim and len(arr) != self.dim:
            raise ValueError(f"Expected dim={self.dim}, got {len(arr)}")
        return struct.pack(f"{len(arr)}f", *arr)

    class comparator_factory(UserDefinedType.Comparator):
        def cosine_distance(self, other):
            # sqlite-vec 使用 embedding MATCH ? 进行搜索
            # 但 SQLAlchemy 无法直接表达 MATCH，因此我们改用辅助函数或 raw SQL
            # 所以：**不在此处实现距离函数，而是由 VecItemManager 负责搜索**
            raise NotImplementedError("Use VecItemManager.search() instead of direct comparison")

        def l2_distance(self, other):
            raise NotImplementedError("Use VecItemManager.search() instead")


# 注册类型(可选，主要用于反射)
ischema_names["vector"] = VectorSqlite


# 普通表：只存原始数据(vector 以 BLOB 存，但不用于搜索)
class VecItem(SQLModel, table=True):
    __tablename__ = "vec_items"
    id: int | None = Field(default=None, primary_key=True)
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column("embedding", VectorSqlite(dim=8))  # 存为 BLOB
    )
    content: str | None = Field(default=None)


class VecItemManager:
    def __init__(self, engine, conn: sqlite3.Connection, table_name: str = "vec_items", dim: int = 8):
        self.engine = engine
        self.conn = conn
        self.table_name = table_name
        self.dim = dim
        self._init_sqlite_vec()
        self._create_virtual_table()

    def _init_sqlite_vec(self):
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)
        self.conn.enable_load_extension(False)

    def _create_virtual_table(self):
        self.conn.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS {self.table_name}_vec 
            USING vec0(embedding float[{self.dim}] distance_metric=cosine)
        """)
        self.conn.commit()

    def add_item(self, item_id: int, vector: list[float], content: str | None = None):
        # 1. 插入到普通表(用于存储元数据)
        with Session(self.engine) as session:
            item = VecItem(id=item_id, embedding=vector, content=content)
            session.add(item)
            session.commit()

        # 2. 插入到虚拟表(用于向量搜索)
        blob = struct.pack(f"{len(vector)}f", *np.array(vector, dtype=np.float32))
        self.conn.execute(
            f"INSERT INTO {self.table_name}_vec(rowid, embedding) VALUES (?, ?)",
            (item_id, blob)
        )
        self.conn.commit()

    def search(self, query_vector: list[float], limit: int = 5):
        blob = struct.pack(f"{len(query_vector)}f", *np.array(query_vector, dtype=np.float32))
        cursor = self.conn.execute(f"""
            SELECT rowid, distance
            FROM {self.table_name}_vec
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
        """, (blob, limit))
        results = []
        for rowid, distance in cursor:
            with Session(self.engine) as session:
                item = session.get(VecItem, rowid)
                if item:
                    results.append({
                        "item": item,
                        "distance": distance,
                        "similarity": 1 - distance
                    })
        return results
    def get_all_items(self) -> list[VecItem]:
        """获取所有项目"""
        with Session(self.engine) as session:
            stmt = select(VecItem)
            return session.exec(stmt).all()
    # 其他方法如 delete_item, get_item 等可保留

# 使用示例
if __name__ == "__main__":
    import sqlite3
    
    # 初始化SQLite连接
    conn = sqlite3.connect(":memory:")
    # 创建SQLModel引擎
    engine = create_engine("sqlite://", creator=lambda: conn)
    
    # 创建表
    SQLModel.metadata.create_all(engine)
    
    # 创建管理器
    manager = VecItemManager(engine, conn, dim=8)
    
    # 准备数据
    items = [
        (1, [-0.200, 0.250, 0.341, -0.211, 0.645, 0.935, -0.316, -0.924], "item_1"),
        (2, [0.443, -0.501, 0.355, -0.771, 0.707, -0.708, -0.185, 0.362], "item_2"),
        (3, [0.716, -0.927, 0.134, 0.052, -0.669, 0.793, -0.634, -0.162], "item_3"),
        (4, [-0.710, 0.330, 0.656, 0.041, -0.990, 0.726, 0.385, -0.958], "item_4"),
    ]
    query = [-0.710, 0.330, 0.656, 0.041, -0.990, 0.726, 0.385, -0.958]
    
    # 添加数据
    for item_id, vector, content in items:
        manager.add_item(item_id, vector, content)
    
    # 测试获取所有项目
    print("所有项目:")
    all_items = manager.get_all_items()
    for item in all_items:
        print(f"ID: {item.id}, 内容: {item.content}, 向量: {item.embedding}")
    print()
    
    # 搜索
    results = manager.search(query, limit=3)
    
    print("搜索结果:")
    for i, result in enumerate(results, 1):
        item:VecItem = result['item']
        distance = result['distance']
        similarity = result['similarity']
        
        print(f"结果 {i}:")
        print(f"  ID: {item.id}")
        print(f"  内容: {item.content}")
        print(f"  向量: {item.embedding}")
        print(f"  距离: {distance:.4f}")
        print(f"  相似度: {similarity:.8f}")
        print()
  