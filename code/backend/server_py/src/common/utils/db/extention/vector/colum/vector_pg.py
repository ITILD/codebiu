from sqlalchemy import String
from sqlalchemy.dialects.postgresql.base import ischema_names
from sqlalchemy.types import UserDefinedType, Float
import numpy as np

class VectorPG(UserDefinedType):
    """PostgreSQL 原生 vector 类型实现"""
    cache_ok = True  # 声明类型可缓存以提高性能
    _string = String()  # 内部使用String类型处理文本转换

    def __init__(self, dim=1024):
        """初始化向量类型
        Args:
            dim (int, optional): 向量维度。None表示动态维度
        """
        super(UserDefinedType, self).__init__()
        self.dim = dim  # 存储向量维度

    def get_col_spec(self, **kw):
        """生成DDL语句中的类型定义"""
        if self.dim is None:
            return "VECTOR"  # 无维度限制的向量类型
        return f"VECTOR({self.dim})"  # 带维度限制的向量类型

    def bind_processor(self, dialect):
        """返回处理绑定参数的函数"""
        return self._to_db  # 使用_to_db方法处理写入数据库的转换

    def result_processor(self, dialect, coltype):
        """返回处理查询结果的函数"""
        def process(value):
            """将数据库中的向量字符串转换为numpy数组
            格式示例: [1.0,2.0,3.0] -> np.array([1.0, 2.0, 3.0])
            """
            return np.fromstring(value[1:-1], sep=',', dtype=np.float32) if value else None
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
        3. 转换为PostgreSQL向量格式字符串
        """
        arr = np.asarray(value, dtype=">f4").flatten()  # 转换为大端序float32数组
        if self.dim and len(arr) != self.dim:
            raise ValueError(f"维度必须为 {self.dim}")  # 维度校验
        return "[" + ",".join(map(str, arr)) + "]"  # 转换为[1.0,2.0,3.0]格式

    class comparator_factory(UserDefinedType.Comparator):
        """自定义比较操作符工厂类"""
        
        def l2(self, other):
            """L2距离(欧氏距离)运算符 <-> 
            返回两个向量之间的欧氏距离
            越小表示越相似
            """
            return self.op("<->", return_type=Float)(other)

        def ip(self, other):
            """最大内积运算符 <#> 
            返回负内积(用于近似最近邻搜索)
            值越小表示相似度越高
            """
            return self.op("<#>", return_type=Float)(other)

        def cosine(self, other):
            """余弦距离运算符 <=>
            返回: 1 - 余弦相似度
            值越小表示相似度越高
            """
            return self.op("<=>", return_type=Float)(other)

        def l1(self, other):
            """L1距离(曼哈顿距离)运算符 <+>
            返回两个向量之间的曼哈顿距离
            越小表示越相似
            """
            return self.op("<+>", return_type=Float)(other)

# 注册类型到SQLAlchemy的类型系统
ischema_names["vector"] = VectorPG