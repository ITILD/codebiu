from neo4j import GraphDatabase, AsyncDriver
from common.utils.db.do.db_config import Neo4jConfig
from common.utils.db.session.interface.db_graph_interface import DBGraphInterface


class DBGraphNeo4j(DBGraphInterface):
    """
    Neo4j图数据库实现
    封装图数据库操作
    """

    async_graph: AsyncDriver = None

    def __init__(self, neo4j_config: Neo4jConfig):
        """
        初始化Neo4j图数据库连接

        Args:
            neo4j_config: Neo4j数据库配置对象
        """
        self.neo4j_config = neo4j_config
        self.async_graph: AsyncDriver = None
        self.uri = f"bolt://{neo4j_config.host}:{neo4j_config.port}"

    def connect(self, log_bool=False):
        """
        建立数据库连接

        Args:
            log_bool: 是否启用日志
        """
        try:
            # 创建Neo4j驱动程序实例
            self.async_graph = GraphDatabase.driver(
                self.uri, auth=(self.neo4j_config.user, self.neo4j_config.password)
            )

            if log_bool:
                print(f"Neo4j数据库连接成功: {self.uri}")
        except Exception as e:
            raise Exception(f"Neo4j数据库连接失败: {e}")

    async def is_connected(self):
        """
        检查连接状态

        Returns:
            bool: 如果连接有效则返回True，否则返回False
        """
        if not self.async_graph:
            return False
        try:
            # 尝试验证连接
            async with self.async_graph.session() as session:
                await session.run("RETURN 1")
            return True
        except Exception:
            return False

    async def reconnect(self):
        """
        重新连接数据库
        """
        await self.disconnect()
        self.connect()

    async def disconnect(self):
        """
        断开数据库连接
        """
        if self.async_graph:
            await self.async_graph.close()
            self.driver = None

    async def get_info(self):
        """
        获取数据库信息

        Returns:
            dict: 包含数据库信息的字典
        """
        connected = await self.is_connected()
        return {
            "type": "Neo4j",
            "uri": self.uri,
            "connected": connected,
        }

    async def execute_query(self, query: str, parameters: dict | None = None):
        """
        执行Cypher查询

        Args:
            query: Cypher查询语句
            parameters: 查询参数

        Returns:
            查询结果
        """
        try:
            async with self.async_graph.session() as session:
                result = await session.run(query, parameters)
                # 获取所有记录
                records = await result.data()
                return records
        except Exception as e:
            raise Exception(f"查询执行失败: {e}")

    async def match_query(self, query: str, params: dict | None = None) -> list[dict]:
        """异步执行Cypher查询并返回记录列表"""
        try:
            async with self.driver.session() as session:
                result = await session.run(query, params)
                results = []
                async for record in result:
                    data = record.data()
                    results.append(data)
                return results
        except Exception as e:
            raise Exception(f"查询执行失败: {e}")
