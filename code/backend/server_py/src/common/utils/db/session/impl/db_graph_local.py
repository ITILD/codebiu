from kuzu import AsyncConnection, Database
from common.utils.db.do.db_config import GraphLocalConfig
from common.utils.db.session.interface.db_graph_interface import DBGraphInterface
import logging
from bidict import bidict
from pydantic import BaseModel
from pydantic.fields import FieldInfo

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

    async def check_table_exists(self, table_name: str) -> bool:
        """
        检查表是否存在

        Args:
            table_name: 表名

        Returns:
            bool: 如果表存在则返回True，否则返回False
        """
        try:
            # 检查指定的表是否存在于 Kùzu 数据库中
            result = await self.async_graph.execute("CALL show_tables() RETURN *;")
            arr = result.get_as_arrow()

            # 获取表名列表并检查是否包含指定的表名（忽略大小写）
            table_name_list = arr["name"].to_pylist()
            return table_name.lower() in table_name_list
        except Exception as e:
            logger.error(f"检查表 {table_name} 是否存在时出错: {e}")
            return False

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
            if await self.check_table_exists(table_name):
                logger.warning(f"表 {table_name} 已存在，跳过创建")
                return
            # 构建schema
            schema = ""
            for name, field in schema_cls.model_fields.items():
                field: FieldInfo
                sql_type, _ = await self._convert_py_type_to_sql_type(
                    field.annotation.__name__, None
                )
                if field.primary_key is True:
                    schema += f"{name} {sql_type} PRIMARY KEY, "
                else:
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
            if await self.check_table_exists(table_name):
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

    async def add_node(self, data: BaseModel) -> None:
        """
        添加节点到图数据库（使用 CREATE）

        Args:
            data: Pydantic 模型实例，其类名作为节点标签
        """
        # 安全处理标签名：仅允许字母、数字、下划线
        label = data.__class__.__name__
        if not label.replace("_", "").isalnum():
            raise ValueError(f"Invalid label name: {label}")

        # 使用参数化属性：{prop: $prop}
        props = ", ".join(f"{k}: ${k}" for k in data.model_dump().keys())
        query = f"CREATE (n:`{label}` {{{props}}})"

        await self.async_graph.execute(query, data.model_dump())

    async def add_edge(self, data: BaseModel):
        """添加关系数据 CREATE (a:Label1 {uuid: $id1})-[:REL_TYPE {props}]->(b:Label2 {uuid: $id2})"""
        # 安全处理标签名：仅允许字母、数字、下划线
        label = data.__class__.__name__.lower()
        if not label.replace("_", "").isalnum():
            raise ValueError(f"Invalid label name: {label}")
        # node_source_field_name = "source"
        # node_target_field_name = "target"
        node_source_query = f"MATCH (a:{data.source.__class__.__name__.lower()} {{uuid: '{data.source.uuid}'}})\n"
        node_target_query = f"MATCH (b:{data.target.__class__.__name__.lower()} {{uuid: '{data.target.uuid}'}})\n"
        # edge_query = f"-[:{label} {{{props}}}]->"
        data_dict = data.model_dump(exclude={"source", "target"})
        props = ""
        for k in data_dict.keys():
            props += f"{k}: ${k}, "
        props = props.rstrip(", ")
        if props:
            props = f"{{{props}}}"
        edge_query = f"MERGE (a)-[:{label} {props}]->(b)"
        query = f" {node_source_query}{node_target_query}{edge_query}"
        await self.async_graph.execute(query, data_dict)

    async def query_node_by_uuid(
        self, schema_cls: type[BaseModel], node_uuid: str
    ) -> list[BaseModel]:
        """
        根据节点 UUID 查询图数据库中的节点，并返回其对应 Pydantic 模型实例列表。
        """
        table_name = schema_cls.__name__.lower()
        # 使用参数化查询防止 Cypher 注入（假设驱动支持）
        query = f"MATCH (n:{table_name} {{uuid: $node_uuid}}) RETURN n"
        result = await self.async_graph.execute(
            query, parameters={"node_uuid": node_uuid}
        )
        return schema_cls.model_validate(result.get_all()[0][0])
    
    # 获取关联
    async def query_single_step_graph_by_node(self, node_uuid: str) -> list[dict]:
        """
        根据节点 UUID 查询图数据库中的单步关联关系。
        """
        query = f"""
        MATCH (n)-[r]->(m)
        WHERE n.uuid = $node_uuid
        RETURN r, m
        """
        result = await self.async_graph.execute(
            query, parameters={"node_uuid": node_uuid}
        )
        result_db = result.get_all()
        # 返回list dict
        result = []
        for r, m in result_db:
            result.append({
                "edge": r,
                "node": m,
            })
        return result

    async def drop_table_node(self, table_name):
        """删除表"""
        await self.async_graph.execute(f"DROP TABLE  IF EXISTS {table_name}")

    async def list_tables(self):
        """列出所有表"""
        tables = await self.async_graph.execute("CALL show_tables() RETURN *;")
        tables_list = tables.get_all()
        return tables_list

    async def list_tables_edges(self):
        """列出所有关系表"""
        tables = await self.async_graph.execute(
            "CALL show_tables() WHERE type = 'REL' RETURN *;"
        )
        return tables

    async def list_tables_nodes(self):
        """列出所有关系表"""
        tables = await self.async_graph.execute(
            "CALL show_tables() WHERE type = 'NODE' RETURN *;"
        )
        return tables

    async def drop_tables_all(self):
        """清空标签和数据  kuzu必须先清理REL 再NODE"""
        # tables_list = await self.list_tables()
        # for table in tables_list:
        #     await self.drop_table_node(table[1])
        tables_edges = await self.list_tables_edges()
        for table_edge in tables_edges:
            await self.drop_table_node(table_edge[1])
        tables_nodes = await self.list_tables_nodes()
        for table_node in tables_nodes:
            await self.drop_table_node(table_node[1])

    async def clear_data(self):
        """TODO 清空数据"""
        await self.async_graph.execute("MATCH (n) DETACH DELETE n")
