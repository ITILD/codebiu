from sqlalchemy import String
from sqlalchemy.dialects.sqlite.base import ischema_names
from sqlalchemy.types import UserDefinedType, Float
import numpy as np
import json


class VectorSqlite(UserDefinedType):
    """SQLite 向量类型实现 - 使用JSON格式存储向量数据
    支持sqlite-vec扩展的distance_metric参数：cosine, l2, hamming
    """
    cache_ok = True  # 声明类型可缓存以提高性能
    _string = String()  # 内部使用String类型处理文本转换

    def __init__(self, dim=1024, distance_metric="cosine"):
        """初始化向量类型
        Args:
            dim (int, optional): 向量维度。None表示动态维度
            distance_metric (str, optional): 距离度量类型，支持：cosine, l2, hamming
        """
        super(UserDefinedType, self).__init__()
        self.dim = dim  # 存储向量维度
        self.distance_metric = distance_metric  # 存储距离度量类型
        
        # 验证距离度量参数
        if distance_metric not in ["cosine", "l2", "hamming"]:
            raise ValueError(f"不支持的distance_metric: {distance_metric}，支持: cosine, l2, hamming")

    def get_col_spec(self, **kw):
        """生成DDL语句中的类型定义
        SQLite中向量存储为TEXT格式(JSON字符串)
        """
        return "TEXT"  # SQLite中存储为JSON字符串

    def bind_processor(self, dialect):
        """返回处理绑定参数的函数"""
        return self._to_db  # 使用_to_db方法处理写入数据库的转换

    def result_processor(self, dialect, coltype):
        """返回处理查询结果的函数"""
        def process(value):
            """将数据库中的JSON字符串转换为numpy数组
            格式示例: '[1.0, 2.0, 3.0]' -> np.array([1.0, 2.0, 3.0])
            """
            if value is None:
                return None
            # 解析JSON字符串为Python列表
            arr_list = json.loads(value)
            # 转换为numpy数组
            return np.array(arr_list, dtype=np.float32)
        return process
    
    def literal_processor(self, dialect):
        """返回处理SQL字面量的函数"""
        string_literal_processor = self._string._cached_literal_processor(dialect)

        def process(value):
            """处理SQL语句中的字面量表达式"""
            return string_literal_processor(self._to_db(value))

        return process

    def _to_db(self, value):
        """将Python对象转换为数据库存储格式
        1. 转换为numpy数组并展平
        2. 验证维度一致性
        3. 转换为JSON字符串格式(用于普通表存储)
        """
        if value is None:
            return None
        
        # 转换为numpy数组
        arr = np.asarray(value, dtype=np.float32).flatten()
        
        # 验证维度一致性
        if self.dim and len(arr) != self.dim:
            raise ValueError(f"维度必须为 {self.dim}")
        
        # 转换为JSON字符串格式(sqlite-vec扩展期望JSON格式)
        # 示例: [1.0, 2.0, 3.0] -> '[1.0, 2.0, 3.0]'
        return json.dumps(arr.tolist())
    
    def get_virtual_table_sql(self, table_name: str, column_name: str = "embedding") -> str:
        """生成创建sqlite-vec虚拟表的SQL语句
        
        Args:
            table_name: 虚拟表名称
            column_name: 向量列名称
            
        Returns:
            SQL语句字符串
            
        Example:
            >>> vector_type = VectorSqlite(dim=8, distance_metric="cosine")
            >>> sql = vector_type.get_virtual_table_sql("vec_examples", "sample_embedding")
            >>> print(sql)
            CREATE VIRTUAL TABLE vec_examples USING vec0(
                sample_embedding float[8] distance_metric=cosine
            )
        """
        if self.dim is None:
            raise ValueError("创建虚拟表时必须指定向量维度")
        
        return f"""CREATE VIRTUAL TABLE {table_name} USING vec0(
    {column_name} float[{self.dim}] distance_metric={self.distance_metric}
)"""

    class comparator_factory(UserDefinedType.Comparator):
        """自定义比较操作符工厂类
        注意：SQLite原生不支持向量运算，这些操作符主要用于语法兼容
        实际向量搜索需要通过sqlite-vec扩展的MATCH操作符实现
        """
        
        def match(self, other):
            """sqlite-vec扩展的MATCH操作符
            用于向量相似度搜索，支持多种距离度量
            语法: embedding MATCH query_vector
            返回: 距离值(越小表示越相似)
            """
            return self.op("MATCH", return_type=Float)(other)


# 注册类型到SQLAlchemy的类型系统
ischema_names["vector"] = VectorSqlite