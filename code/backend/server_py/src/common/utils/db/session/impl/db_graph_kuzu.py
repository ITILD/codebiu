from kuzu import AsyncConnection, Database
from common.utils.db.do.db_config import KuzuConfig
from common.utils.db.session.interface.db_graph_interface import DBGraphInterface

# https://kuzudb.github.io/docs/client-apis/python/
class DBGraphKuzu(DBGraphInterface):
    """
    Kuzu图数据库实现
    封装图数据库操作
    """
    async_graph: AsyncConnection = None

    def __init__(self, kuzu_config: KuzuConfig):
        """
        初始化Kuzu图数据库连接

        Args:
            kuzu_config: Kuzu数据库配置对象
        """
        self.kuzu_config = kuzu_config
        self.database = None
        self.async_graph = None

    def connect(self, log_bool=False):
        """
        建立数据库连接

        Args:
            log_bool: 是否启用日志
        """
        try:
            # 创建Kuzu数据库实例
            self.database = Database(self.kuzu_config.database)
            # 创建连接
            self.async_graph = AsyncConnection(
                self.database,
                # 最大并发查询数
                max_concurrent_queries=4,
            )

            if log_bool:
                print(f"Kuzu数据库连接成功: {self.kuzu_config.database}")
        except Exception as e:
            raise Exception(f"Kuzu数据库连接失败: {e}")

    async def is_connected(self):
        """
        检查连接状态

        Returns:
            bool: 如果连接有效则返回True，否则返回False
        """
        return self.connection is not None

    async def reconnect(self):
        """
        重新连接数据库
        """
        await self.disconnect()
        await self.connect()

    async def disconnect(self):
        """
        断开数据库连接
        """
        if self.connection:
            # Kuzu的连接不需要显式关闭
            self.connection = None
        if self.database:
            # Kuzu的数据库不需要显式关闭
            self.database = None

    async def get_info(self):
        """
        获取数据库信息

        Returns:
            dict: 包含数据库信息的字典
        """
        return {
            "type": "Kuzu",
            "database": self.kuzu_config.database,
            "connected": await self.is_connected(),
        }

    async def execute_query(self, query: str, parameters=None):
        """
        执行Cypher查询

        Args:
            query: Cypher查询语句
            parameters: 查询参数

        Returns:
            查询结果
        """
        if not self.connection:
            raise Exception("数据库未连接")

        try:
            if parameters:
                result = await self.connection.execute(query, parameters)
            else:
                result = await self.connection.execute(query)
            return result
        except Exception as e:
            raise Exception(f"查询执行失败: {e}")
