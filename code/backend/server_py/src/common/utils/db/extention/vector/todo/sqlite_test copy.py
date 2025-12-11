from sqlmodel import SQLModel, Field, Session, create_engine, select
from sqlalchemy import String, text
from sqlalchemy.dialects.sqlite.base import ischema_names
from sqlalchemy.types import UserDefinedType, Float
import numpy as np
import struct
import sqlite3
import json


class VectorSqlite(UserDefinedType):
    """SQLite sqlite-vec 向量类型实现"""
    cache_ok = True
    _string = String()

    def __init__(self, dim=None):
        """
        Args:
            dim (int, optional): 向量维度。None表示动态维度
        """
        super(UserDefinedType, self).__init__()
        self.dim = dim

    def get_col_spec(self, **kw):
        """在SQLite中，向量存储为TEXT(JSON字符串格式)"""
        return "TEXT"  # SQLite中存储为JSON字符串

    def bind_processor(self, dialect):
        """返回处理绑定参数的函数"""
        return self._to_db

    def result_processor(self, dialect, coltype):
        """返回处理查询结果的函数"""
        def process(value):
            """将数据库中的JSON字符串转换为numpy数组"""
            if value is None:
                return None
            if isinstance(value, bytes):
                # 如果是bytes格式(sqlite-vec)，转换为数组
                return self._from_bytes(value)
            elif isinstance(value, str):
                # 如果是JSON字符串格式
                arr = json.loads(value)
                return np.array(arr, dtype=np.float32)
            else:
                # 如果已经是数组格式
                return np.array(value, dtype=np.float32)
        return process

    def literal_processor(self, dialect):
        """返回处理SQL字面量的函数"""
        string_literal_processor = self._string._cached_literal_processor(dialect)

        def process(value):
            """处理SQL语句中的字面量表达式"""
            return string_literal_processor(self._to_db(value))

        return process

    def _to_db(self, value):
        """将Python对象转换为数据库存储格式"""
        if value is None:
            return None
        
        # 转换为numpy数组
        arr = np.asarray(value, dtype=np.float32).flatten()
        if self.dim and len(arr) != self.dim:
            raise ValueError(f"维度必须为 {self.dim}")
        
        # SQLite sqlite-vec 期望的是序列化的bytes
        # 但存储在普通表中时通常用JSON字符串
        return json.dumps(arr.tolist())

    def _to_bytes(self, arr):
        """转换为bytes格式(用于sqlite-vec)"""
        return struct.pack("%sf" % len(arr), *arr)

    def _from_bytes(self, data):
        """从bytes格式转换回数组"""
        return list(struct.unpack("%sf" % (len(data) // 4), data))

    class comparator_factory(UserDefinedType.Comparator):
        """自定义比较操作符工厂类"""
        
        def cosine_distance(self, other):
            """余弦距离比较(sqlite-vec使用MATCH操作)"""
            from sqlalchemy import func
            # 使用sqlite-vec扩展的MATCH操作符进行余弦距离计算
            # 注意：这需要sqlite-vec扩展支持
            return func.cosine_distance(self, other)

        def l2_distance(self, other):
            """L2距离比较"""
            from sqlalchemy import func
            # 使用sqlite-vec扩展的MATCH操作符进行L2距离计算
            return func.l2_distance(self, other)

# 注册到SQLite类型系统
ischema_names["vector"] = VectorSqlite

# 自定义SQL函数实现
def register_vector_functions(conn):
    """注册自定义向量函数到SQLite连接"""
    
    def cosine_distance_func(vec1_json, vec2_json):
        """计算两个向量的余弦距离"""
        if vec1_json is None or vec2_json is None:
            return None
        
        try:
            vec1 = json.loads(vec1_json)
            vec2 = json.loads(vec2_json)
            
            # 转换为numpy数组
            v1 = np.array(vec1, dtype=np.float32)
            v2 = np.array(vec2, dtype=np.float32)
            
            # 计算余弦相似度
            dot_product = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            
            if norm1 == 0 or norm2 == 0:
                return 1.0  # 如果向量长度为0，距离为1
            
            cosine_similarity = dot_product / (norm1 * norm2)
            # 余弦距离 = 1 - 余弦相似度
            return float(1.0 - cosine_similarity)
        except Exception:
            return None
    
    def l2_distance_func(vec1_json, vec2_json):
        """计算两个向量的L2距离"""
        if vec1_json is None or vec2_json is None:
            return None
        
        try:
            vec1 = json.loads(vec1_json)
            vec2 = json.loads(vec2_json)
            
            # 转换为numpy数组
            v1 = np.array(vec1, dtype=np.float32)
            v2 = np.array(vec2, dtype=np.float32)
            
            # 计算L2距离
            return float(np.linalg.norm(v1 - v2))
        except Exception:
            return None
    
    # 注册函数到SQLite连接
    conn.create_function("cosine_distance", 2, cosine_distance_func)
    conn.create_function("l2_distance", 2, l2_distance_func)


# SQLite向量搜索助手类
class SqliteVecHelper:
    """SQLite sqlite-vec 功能助手"""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._init_sqlite_vec()
    
    def _init_sqlite_vec(self):
        """初始化sqlite-vec扩展"""
        self.conn.enable_load_extension(True)
        import sqlite_vec
        sqlite_vec.load(self.conn)
        self.conn.enable_load_extension(False)
    
    def create_vector_table(self, table_name: str, dim: int, distance_metric: str = "cosine"):
        """创建向量虚拟表"""
        virtual_table_sql = f"""
            CREATE VIRTUAL TABLE {table_name}_virtual 
            USING vec0(embedding float[{dim}] distance_metric={distance_metric})
        """
        self.conn.execute(virtual_table_sql)
        self.conn.commit()
    
    def insert_vector(self, table_name: str, rowid: int, vector: list[float]):
        """插入向量到虚拟表"""
        serialized_vector = self._serialize_vector(vector)
        self.conn.execute(
            f"INSERT INTO {table_name}_virtual(rowid, embedding) VALUES (?, ?)",
            (rowid, serialized_vector)
        )
        self.conn.commit()
    
    def search_vectors(self, table_name: str, query_vector: list[float], limit: int = 10):
        """搜索相似向量"""
        serialized_query = self._serialize_vector(query_vector)
        cursor = self.conn.execute(
            f"""
            SELECT rowid, distance
            FROM {table_name}_virtual
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
            """,
            (serialized_query, limit)
        )
        return cursor.fetchall()
    
    def _serialize_vector(self, vector: list[float]) -> bytes:
        """序列化向量为bytes"""
        return struct.pack("%sf" % len(vector), *vector)
    
    def _deserialize_vector(self, data: bytes) -> list[float]:
        """反序列化bytes为向量"""
        return list(struct.unpack("%sf" % (len(data) // 4), data))


from sqlalchemy import Column

class VecItem(SQLModel, table=True):
    """向量项目模型 - 支持SQLite sqlite-vec"""
    __tablename__ = "vec_items"
    
    id: int | None = Field(default=None, primary_key=True)
    # 使用VectorSqlite类型存储向量数据
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(VectorSqlite(dim=8))  # 指定向量维度为8
    )
    # 元数据字段
    content: str | None = Field(default=None)
    metadata_: str | None = Field(default=None, alias="metadata")


class VecItemManager:
    """向量项目管理器"""
    
    def __init__(self, engine, sqlite_vec_helper: SqliteVecHelper):
        self.engine = engine
        self.vec_helper = sqlite_vec_helper
        self.table_name = "vec_items"
    
    def add_item(self, item_id: int, vector: list[float], content: str | None = None, metadata: str | None = None):
        """添加向量项目"""
        # 插入到普通表
        with Session(self.engine) as session:
            vec_item = VecItem(
                id=item_id,
                embedding=vector,  # 直接使用VectorSqlite类型
                content=content,
                metadata_=metadata
            )
            session.add(vec_item)
            session.commit()
        
        # 同步到虚拟表用于搜索
        self.vec_helper.insert_vector(self.table_name, item_id, vector)
    
    def search(self, query_vector: list[float], limit: int = 5) -> list[dict]:
        """搜索相似向量"""
        # 在虚拟表中搜索
        search_results = self.vec_helper.search_vectors(
            self.table_name, query_vector, limit
        )
        
        results = []
        for rowid, distance in search_results:
            # 从普通表获取完整信息
            with Session(self.engine) as session:
                # 使用SQLModel的select查询
                stmt = select(VecItem).where(VecItem.id == rowid)
                item = session.exec(stmt).first()
                
                if item:
                    results.append({
                        'item': item,
                        'vector': item.embedding,  # 直接使用VectorSqlite类型返回的向量
                        'distance': distance,
                        'similarity': 1 - distance
                    })
        
        return results
    
    def search_with_cosine_distance(self, query_vector: list[float], limit: int = 5) -> list[dict]:
        """使用SQLAlchemy的cosine_distance操作符搜索相似向量"""
        from sqlalchemy import func
        
        # 将查询向量转换为JSON字符串格式
        query_vector_json = json.dumps(query_vector)
        
        with Session(self.engine) as session:
            # 使用cosine_distance进行查询
            stmt = select(
                VecItem,
                func.cosine_distance(VecItem.embedding, query_vector_json).label('distance')
            ).order_by(
                func.cosine_distance(VecItem.embedding, query_vector_json)
            ).limit(limit)
            
            results = []
            for item, distance in session.exec(stmt):
                results.append({
                    'item': item,
                    'vector': item.embedding,
                    'distance': distance,
                    'similarity': 1 - distance if distance is not None else 0
                })
            
            return results
    
    def get_item(self, item_id: int) -> VecItem | None:
        """获取单个项目"""
        with Session(self.engine) as session:
            stmt = select(VecItem).where(VecItem.id == item_id)
            return session.exec(stmt).first()
    
    def get_all_items(self) -> list[VecItem]:
        """获取所有项目"""
        with Session(self.engine) as session:
            stmt = select(VecItem)
            return session.exec(stmt).all()
    
    def delete_item(self, item_id: int) -> bool:
        """删除项目"""
        with Session(self.engine) as session:
            stmt = select(VecItem).where(VecItem.id == item_id)
            item = session.exec(stmt).first()
            if item:
                session.delete(item)
                session.commit()
                # 同时从虚拟表中删除
                self.vec_helper.conn.execute(
                    f"DELETE FROM {self.table_name}_virtual WHERE rowid = ?",
                    (item_id,)
                )
                self.vec_helper.conn.commit()
                return True
            return False


# 使用示例
if __name__ == "__main__":
    import sqlite3
    
    # 初始化SQLite连接
    conn = sqlite3.connect(":memory:")
    
    # 注册自定义向量函数
    register_vector_functions(conn)
    
    # 创建助手
    vec_helper = SqliteVecHelper(conn)
    vec_helper.create_vector_table("vec_items", dim=8, distance_metric="cosine")
    
    # 创建SQLModel引擎
    engine = create_engine("sqlite://", creator=lambda: conn)
    
    # 创建表
    SQLModel.metadata.create_all(engine)
    
    # 创建管理器
    manager = VecItemManager(engine, vec_helper)
    
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
        item = result['item']
        distance = result['distance']
        similarity = result['similarity']
        vector = result['vector']
        
        print(f"结果 {i}:")
        print(f"  ID: {item.id}")
        print(f"  内容: {item.content}")
        print(f"  向量: {vector}")
        print(f"  距离: {distance:.4f}")
        print(f"  相似度: {similarity:.8f}")
        print()
    
    # 测试获取单个项目
    print("获取单个项目:")
    single_item = manager.get_item(1)
    if single_item:
        print(f"ID: {single_item.id}, 内容: {single_item.content}")
    print()
    
    # 测试删除项目
    print("删除项目ID=2:")
    if manager.delete_item(2):
        print("删除成功")
        remaining_items = manager.get_all_items()
        print(f"剩余项目数量: {len(remaining_items)}")
    else:
        print("删除失败")
    
    # 测试使用cosine_distance进行搜索
    print("\n使用cosine_distance进行搜索:")
    cosine_results = manager.search_with_cosine_distance(query, limit=3)
    
    print("cosine_distance搜索结果:")
    for i, result in enumerate(cosine_results, 1):
        item = result['item']
        distance = result['distance']
        similarity = result['similarity']
        vector = result['vector']
        
        print(f"结果 {i}:")
        print(f"  ID: {item.id}")
        print(f"  内容: {item.content}")
        print(f"  向量: {vector}")
        print(f"  距离: {distance:.4f}")
        print(f"  相似度: {similarity:.8f}")
        print()

# https://alexgarcia.xyz/sqlite-vec/python.html