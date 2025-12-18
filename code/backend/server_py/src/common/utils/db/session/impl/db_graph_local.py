from kuzu import AsyncConnection, Database
from common.utils.db.do.db_config import GraphLocalConfig
from common.utils.db.session.interface.db_graph_interface import DBGraphInterface
import logging
from bidict import bidict
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# https://kuzudb.github.io/docs/client-apis/python/
class DBGraphLocal(DBGraphInterface):
    """
    graph_local图数据库实现
    封装图数据库操作
    """

    async_graph: AsyncConnection = None
    # 类型转换映射 双向dict
    py2sql_type_bidict: bidict = bidict(
        {
            "bool": "BOOL",
            "int": "INT64",
            "float": "DOUBLE",
            "str": "STRING",
            "datetime": "TIMESTAMP",
            "date": "DATE",
            "timedelta": "INTERVAL",
            "uuid": "UUID",
            "list": "LIST",
            "dict": "MAP",
        }
    )

    def __init__(self, graph_local_config: GraphLocalConfig):
        """
        初始化graph_local图数据库连接

        Args:
            graph_local_config: graph_local数据库配置对象
        """
        self.graph_local_config = graph_local_config
        self.database = None
        self.async_graph = None

    def connect(self, log_bool=False):
        """
        建立数据库连接

        Args:
            log_bool: 是否启用日志
        """
        try:
            # 创建graph_local数据库实例
            self.database = Database(self.graph_local_config.database)
            # 创建连接
            self.async_graph = AsyncConnection(
                self.database,
                # 最大并发查询数
                max_concurrent_queries=4,
            )

            if log_bool:
                logger.info(
                    f"graph_local数据库连接成功: {self.graph_local_config.database}"
                )
        except Exception as e:
            raise Exception(f"graph_local数据库连接失败: {e}")

    async def is_connected(self):
        """
        检查连接状态

        Returns:
            bool: 如果连接有效则返回True，否则返回False
        """
        return self.async_graph is not None

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
        if self.async_graph:
            # graph_local的连接不需要显式关闭
            self.async_graph = None
        if self.database:
            # graph_local的数据库不需要显式关闭
            self.database = None

    async def get_info(self):
        """
        获取数据库信息

        Returns:
            dict: 包含数据库信息的字典
        """
        return {
            "type": "graph_local",
            "database": self.graph_local_config.database,
            "connected": await self.is_connected(),
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
            result = await self.async_graph.execute(query, parameters)
            return result
        except Exception as e:
            raise Exception(f"查询执行失败: {e}")

    async def _convert_py_type_to_sql_type(
        self, py_type: str, data: object
    ) -> tuple[str, object]:
        """
        将 Python 类型名称映射为 SQL 类型，必要时转换数据。

        若未定义映射，则使用 STRING 类型，并将数据转为字符串。

        Args:
            py_type: Python 类型名称（如 'int', 'str'）。
            data: 原始数据值。

        Returns:
            tuple[str, object]: (SQL 类型字符串, 转换后的数据)
        """
        sql_type = self.py2sql_type_bidict.get(py_type)
        if sql_type is None:
            logger.warning(
                f"未定义 Python 类型 {py_type!r} 的 SQL 映射，默认使用 STRING"
            )
            return "STRING", str(data)
        return sql_type, data

    async def is_table_exist(self, table_name: str) -> bool:
        """
        检查表是否存在

        Args:
            table_name: 表名

        Returns:
            bool: 如果表存在则返回True，否则返回False
        """
        """检查指定的表是否存在于 Kùzu 数据库中"""
        result = await self.async_graph.execute("CALL show_tables() RETURN *;")
        return bool(result.get_as_df().iloc[0][0])

    async def create_table_node(self, schema_cls: type[BaseModel]):
        """
        创建表

        Args:
            table_name: 表名
            schema: 表结构定义
            # 备选方案
            # https://github.com/lance-format/lance-graph
            # https://github.com/LadybugDB/ladybug

            # conn.execute("CREATE NODE TABLE User(name STRING PRIMARY KEY, age INT64)")
            # conn.execute("CREATE NODE TABLE City(name STRING PRIMARY KEY, population INT64)")
            # conn.execute("CREATE REL TABLE Follows(FROM User TO User, since INT64)")
            # conn.execute("CREATE REL TABLE LivesIn(FROM User TO City)")
        """
        sql = ""
        try:
            table_name = schema_cls.__name__.lower()
            # 检查表是否存在
            if await self.is_table_exist(table_name):
                logger.warning(f"表 {table_name} 已存在，跳过创建")
                return
            # 构建schema
            schema = ""
            for name, field in schema_cls.model_fields.items():
                sql_type, _ = await self._convert_py_type_to_sql_type(
                    field.annotation.__name__, None
                )
                schema += f"{name} {sql_type}, "
            schema = schema.rstrip(", ")
            sql = f"CREATE NODE TABLE {table_name} ({schema})"
            await self.async_graph.execute(sql)
        except Exception as e:
            logger.info(f"创建表 {table_name}语句{sql} 失败: {e}")
            raise Exception(f"创建表失败: {e}")

    async def create_table_edge(
        self,
        schema_cls: type[BaseModel],
        source_field_name: str = "source",
        target_field_name: str = "target",
    ):
        """

        Args:
            schema_cls: 关系表结构定义
        """
        try:
            table_name = schema_cls.__name__.lower()
            # 检查表是否存在
            if await self.is_table_exist(table_name):
                logger.warning(f"表 {table_name} 已存在，跳过创建")
                return
            # 构建schema   conn.execute("CREATE REL TABLE LivesIn(FROM User TO City)")
            schema_from_to = ""
            schema = ""
            for name, field in schema_cls.model_fields.items():
                if name == source_field_name:
                    schema_from_to = (
                        f"FROM {field.annotation.__name__.lower()} " + schema_from_to
                    )
                elif name == target_field_name:
                    schema_from_to += f"TO {field.annotation.__name__.lower()} "
                else:
                    sql_type, _ = await self._convert_py_type_to_sql_type(
                        field.annotation.__name__, None
                    )
                    schema += f"{name} {sql_type}, "
            schema = schema.rstrip(", ")
            if schema:
                # 关系表至少有一个字段 schema_from_to :FROM User TO User, schema: since INT64
                schema_from_to += ","
            await self.async_graph.execute(
                f"CREATE REL TABLE {table_name} ({schema_from_to}{schema})"
            )
        except Exception as e:
            raise Exception(f"创建关系表失败: {e}")

    async def add_node(self, data: BaseModel):
        """添加数据"""
        table_name = data.__class__.__name__.lower()
        # 构建INSERT语句
        columns = ", ".join(data.model_dump().keys())
        placeholders = ", ".join([f":{col}" for col in data.model_dump().keys()])
        query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        # 执行INSERT语句
        await self.async_graph.execute(query, data.model_dump())

    async def add_edge(self, data: BaseModel):
        """添加关系数据"""
        table_name = data.__class__.__name__.lower()
        # 构建INSERT语句
        columns = ", ".join(data.model_dump().keys())
        placeholders = ", ".join([f":{col}" for col in data.model_dump().keys()])
        query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        # 执行INSERT语句
        await self.async_graph.execute(query, data.model_dump())

    async def query_node(self, schema_cls: type[BaseModel], node_id: str):
        """查询节点数据"""
        table_name = schema_cls.__name__.lower()
        query = f"MATCH (n:{table_name} {{id: '{node_id}'}}) RETURN n;"
        result = await self.async_graph.execute(query)
        return result

    # async def get_as_networkx(self, query: str):
    #     """执行查询并返回NetworkX图"""
    #     result = await self.async_graph.execute(query)
    #     return result.get_as_networkx()

    async def drop_table_node(self, table_name):
        """删除表"""
        await self.async_graph.execute(f"DROP TABLE  IF EXISTS {table_name}")

    async def list_tables(self):
        """列出所有表"""
        tables = await self.async_graph.execute("CALL show_tables() RETURN *;")
        return tables

    async def drop_tables_all(self):
        """清空标签和数据"""
        tables = await self.list_tables()
        for table in tables:
            await self.drop_table_node(table["name"])

    async def clear_data(self):
        """清空数据"""
        await self.async_graph.execute("MATCH (n) DETACH DELETE n")
