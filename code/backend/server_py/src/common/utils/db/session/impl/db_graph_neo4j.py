from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.graph import Node, Relationship
from common.utils.db.do.db_config import Neo4jConfig
from common.utils.db.session.interface.db_graph_interface import DBGraphInterface
import logging
from bidict import bidict
from pydantic import BaseModel
from pydantic.fields import FieldInfo

logger = logging.getLogger(__name__)


class DBGraphNeo4j(DBGraphInterface):
    """
    Neo4j图数据库实现
    封装图数据库操作
    """

    async_graph = None
    # 类型转换映射 双向dict
    py2sql_type_bidict: bidict = bidict(
        {
            "bool": "BOOLEAN",
            "int": "INTEGER",
            "float": "FLOAT",
            "str": "STRING",
            "datetime": "LOCALDATETIME",
            "date": "DATE",
            "timedelta": "DURATION",
            "uuid": "STRING_UUID",  # 修改：使用不同的值避免重复
            "list": "LIST",
            "dict": "MAP",
        }
    )

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
            self.async_graph = AsyncGraphDatabase.driver(
                self.uri, auth=(self.neo4j_config.user, self.neo4j_config.password)
            )

            if log_bool:
                logger.info(f"Neo4j数据库连接成功: {self.uri}")
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
            self.async_graph = None

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
                records = []
                async for record in result:
                    records.append(dict(record))
                return records
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
        # 如果是特殊映射，如STRING_UUID，返回标准的STRING类型
        if sql_type == "STRING_UUID":
            return "STRING", data
        return sql_type, data

    async def check_table_exists(self, table_name: str) -> bool:
        """
        检查节点标签是否存在

        Args:
            table_name: 标签名

        Returns:
            bool: 如果标签存在则返回True，否则返回False
        """
        try:
            # Neo4j没有表的概念，使用标签（Label）来表示节点类型
            # 查询特定标签的节点是否存在
            query_node = "CALL db.labels() YIELD label RETURN $table_name IN collect(label) AS exists"
            result = await self.execute_query(query_node, {"table_name": table_name})
            is_exists_node: bool = result[0]["exists"]
            query_edge = "CALL db.relationshipTypes() YIELD relationshipType RETURN $table_name IN collect(relationshipType) AS exists"
            result = await self.execute_query(query_edge, {"table_name": table_name})
            is_exists_edge: bool = result[0]["exists"]
            # 是否存在一个
            is_exists = is_exists_node or is_exists_edge
            return is_exists
        except Exception as e:
            logger.error(f"检查标签 {table_name} 是否存在时出错: {e}")
            return False

    async def create_table_node(self, schema_cls: type[BaseModel]):
        """
        在Neo4j中，节点类型通过标签表示，无需显式创建表结构
        Neo4j是模式自由的，节点属性可以动态添加
        此方法可以作为占位符或用于创建约束
        """
        # Neo4j是模式自由的，无需显式创建表
        # 但我们可以创建约束以确保数据完整性
        table_name = schema_cls.__name__.lower()
        try:
            # 检查标签是否存在（通过查找节点）
            if await self.check_table_exists(table_name):
                logger.warning(f"标签 {table_name} 已存在，跳过创建")
                return

            # 为uuid字段创建唯一约束（如果存在uuid字段）neo4j不需要单独搞表
            if "uuid" in schema_cls.model_fields:
                constraint_name = f"uuid_unique_{table_name}"
                try:
                    # 尝试创建唯一约束
                    await self.execute_query(
                        f"CREATE CONSTRAINT {constraint_name} FOR (n:`{table_name}`) REQUIRE n.uuid IS UNIQUE"
                    )
                except Exception:
                    # 约束可能已存在，忽略错误
                    pass
        except Exception as e:
            logger.info(f"创建节点标签 {table_name} 约束失败: {e}")

    async def create_table_edge(
        self,
        schema_cls: type[BaseModel],
    ):
        """
        Neo4j中关系类型通过关系类型表示，无需显式创建表结构
        """
        # Neo4j是模式自由的，无需显式创建关系表
        # 但我们可以记录关系类型以便管理
        table_name = schema_cls.__name__.lower()
        try:
            # Neo4j中关系类型无需显式创建，直接在添加关系时使用即可
            logger.info(f"关系类型 {table_name} 已准备就绪")
            return True
        except Exception as e:
            raise Exception(f"准备关系类型失败: {e}")

    async def add_node(self, data: BaseModel) -> None:
        """
        添加节点到图数据库（使用 CREATE）

        Args:
            data: Pydantic 模型实例，其类名作为节点标签
        """
        # 安全处理标签名：仅允许字母、数字、下划线
        label = data.__class__.__name__.lower()
        if not label.replace("_", "").isalnum():
            raise ValueError(f"Invalid label name: {label}")

        # 使用参数化属性：{prop: $prop}
        props = ", ".join(f"{k}: ${k}" for k in data.model_dump().keys())
        query = f"CREATE (n:`{label}` {{{props}}})"

        await self.execute_query(query, data.model_dump())

    async def add_edge(self, data: BaseModel):
        """添加关系数据 CREATE (a:Label1 {uuid: $id1})-[:REL_TYPE {props}]->(b:Label2 {uuid: $id2})"""
        # 安全处理标签名：仅允许字母、数字、下划线
        label = data.__class__.__name__.lower()
        if not label.replace("_", "").isalnum():
            raise ValueError(f"Invalid label name: {label}")

        # 获取源节点和目标节点的信息
        data_dict = data.model_dump(exclude={"source", "target"})
        props = ""
        for k in data_dict.keys():
            props += f"{k}: ${k}, "
        props = props.rstrip(", ")
        if props:
            props = f"{{{props}}}"
        else:
            props = "{}"

        # 构建查询语句
        query = f"""
        MATCH (a:`{data.source.__class__.__name__.lower()}` {{uuid: $source_uuid}})
        MATCH (b:`{data.target.__class__.__name__.lower()}` {{uuid: $target_uuid}})
        MERGE (a)-[:`{label}` {props}]->(b)
        """

        # 准备参数
        params = {
            "source_uuid": data.source.uuid,
            "target_uuid": data.target.uuid,
            **data_dict,
        }

        await self.execute_query(query, params)

    async def query_node_by_uuid(
        self, schema_cls: type[BaseModel], node_uuid: str
    ) -> BaseModel:
        """
        根据节点 UUID 查询图数据库中的节点，并返回其对应 Pydantic 模型实例。
        """
        label = schema_cls.__name__.lower()
        # 使用参数化查询防止 Cypher 注入
        query = f"MATCH (n:`{label}` {{uuid: $node_uuid}}) RETURN n"
        result = await self.execute_query(query, {"node_uuid": node_uuid}) 

        if not result:
            return None

        # 提取节点属性并创建模型实例
        node_data:Node = result[0]["n"]  # Neo4j返回的节点数据
        node_data_dict = dict(node_data)
        return schema_cls.model_validate(node_data_dict)
    
    async def query_single_step_graph_by_node(
        self,  node_uuid: str
    ) -> list[BaseModel]:
        """
        根据节点 UUID 查询图数据库中的节点，并返回其对应 Pydantic 模型实例。
        """
        query = """
        MATCH (n{uuid: $node_uuid})
        MATCH (n)-[r]-(m)
        RETURN r,m
        """
        result_list = await self.execute_query(query, {"node_uuid": node_uuid})
        # 返回list dict
        result = []
        for record in result_list:
            r:Relationship = record["r"]
            m:Node = record["m"]
            result.append({
                "edge": dict(r),
                "node": dict(m),
            })
        return result

    async def drop_table_node(self, table_name: str):
        """删除具有特定标签的所有节点及其关系"""
        # 在Neo4j中删除所有具有指定标签的节点
        query = f"MATCH (n:`{table_name}`) DETACH DELETE n"
        await self.execute_query(query)

    async def list_tables(self):
        """列出所有标签（相当于表）"""
        # 查询数据库中所有不同的标签
        # query = "CALL db.labels()"
        query = """MATCH (n)
UNWIND labels(n) AS label
WITH label, count(n) AS count
RETURN label"""
        result = await self.execute_query(query)
        # 返回标签列表
        return [record["label"] for record in result]

    async def list_tables_edges(self):
        """列出所有关系类型"""
        # 查询数据库中所有不同的关系类型
        query = "CALL db.relationshipTypes()"
        result = await self.execute_query(query)
        # 返回关系类型列表
        return [record["relationshipType"] for record in result]

    async def list_tables_nodes(self):
        """列出所有节点标签"""
        # 查询数据库中所有不同的标签
        query = "CALL db.labels()"
        result = await self.execute_query(query)
        # 返回标签列表
        return [record["label"] for record in result]

    async def drop_tables_all(self):
        """清空所有节点和关系"""
        # 删除所有节点及其关系
        query = "MATCH (n) DETACH DELETE n"
        # TODO 删除索引
        await self.execute_query(query)

    async def clear_data(self):
        """清空数据"""
        await self.drop_tables_all()
