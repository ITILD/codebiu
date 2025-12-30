from abc import ABC, abstractmethod
from pydantic import BaseModel


class DBGraphInterface(ABC):
    """
    图数据库接口
    定义了图数据库操作的基本方法
    """

    @abstractmethod
    def __init__(self, config):
        """
        初始化方法。

        子类必须实现此方法，通常用于接收数据库连接所需的配置参数
        (例如：主机地址、端口、用户名、密码、数据库名等)。

        Args:
            config: 数据库配置对象
        """
        raise NotImplementedError("子类必须实现 __init__ 方法")

    @abstractmethod
    def connect(self, log_bool=False):
        """
        建立数据库连接。

        子类需要实现具体的数据库连接逻辑。

        Args:
            log_bool: 是否启用日志
        """
        raise NotImplementedError("子类必须实现 connect 方法")

    @abstractmethod
    async def is_connected(self):
        """
        检查当前数据库连接状态。

        子类需要实现检查连接是否有效、活动的逻辑。

        Returns:
            bool: 如果连接有效则返回True，否则返回False
        """
        raise NotImplementedError("子类必须实现 is_connected 方法")

    @abstractmethod
    async def reconnect(self):
        """
        重新连接数据库。

        通常在连接丢失或需要刷新连接时调用。
        子类需要实现断开现有连接(如果需要)并重新建立连接的逻辑。
        """
        raise NotImplementedError("子类必须实现 reconnect 方法")

    @abstractmethod
    async def disconnect(self):
        """
        断开数据库连接。

        子类需要实现关闭数据库连接并释放相关资源的逻辑。
        """
        raise NotImplementedError("子类必须实现 disconnect 方法")

    @abstractmethod
    async def get_info(self):
        """
        获取数据库相关信息。

        例如：数据库类型、版本、服务器状态、连接参数等。
        子类需要实现获取其特定数据库信息的逻辑。

        Returns:
            dict: 包含数据库信息的字典
        """
        raise NotImplementedError("子类必须实现 get_info 方法")

    @abstractmethod
    async def execute_query(self, query: str, parameters: dict | None = None):
        """
        执行图数据库查询。

        子类需要实现具体的查询执行逻辑。

        Args:
            query: 查询语句(Cypher或其他图查询语言)
            parameters: 查询参数

        Returns:
            查询结果
        """
        raise NotImplementedError("子类必须实现 execute_query 方法")

    @abstractmethod
    async def create_table_node(self, schema_cls: type[BaseModel]):
        """
        创建节点表。

        Args:
            schema_cls: 节点表结构定义类
        """
        raise NotImplementedError("子类必须实现 create_table_node 方法")

    @abstractmethod
    async def create_table_edge(self, schema_cls: type[BaseModel]):
        """
        创建边表。

        Args:
            schema_cls: 边表结构定义类
        """
        raise NotImplementedError("子类必须实现 create_table_edge 方法")

    @abstractmethod
    async def drop_table_node(self, table_name: str):
        """
        删除节点表。

        Args:
            table_name: 表名
        """
        raise NotImplementedError("子类必须实现 drop_table_node 方法")

    @abstractmethod
    async def list_tables(self):
        """
        列出所有表。

        Returns:
            所有表的列表
        """
        raise NotImplementedError("子类必须实现 list_tables 方法")

    @abstractmethod
    async def drop_tables_all(self):
        """
        删除所有表。
        """
        raise NotImplementedError("子类必须实现 drop_tables_all 方法")

    @abstractmethod
    async def clear_data(self):
        """
        清空数据。
        """
        raise NotImplementedError("子类必须实现 clear_data 方法")

    @abstractmethod
    async def add_node(self, node: BaseModel):
        """
        添加节点。

        Args:
            node: 节点对象
        """
        raise NotImplementedError("子类必须实现 add_node 方法")

    @abstractmethod
    async def add_edge(self, edge: BaseModel):
        """
        添加边。

        Args:
            edge: 边对象
        """
        raise NotImplementedError("子类必须实现 add_edge 方法")
    
    @abstractmethod
    async def query_node_by_uuid(self, node_cls: type[BaseModel], node_uuid: str):
        """
        查询节点。

        Args:
            node_cls: 节点类
            node_uuid: 节点UUID

        Returns:
            节点对象
        """
        raise NotImplementedError("子类必须实现 query_node_by_uuid 方法")
    
    @abstractmethod
    async def list_tables_edges(self):
        """
        列出所有边表。

        Returns:
            所有边表的列表
        """
        raise NotImplementedError("子类必须实现 list_tables_edges 方法")
    
    @abstractmethod
    async def check_table_exists(self, table_name: str):
        """
        检查表是否存在。

        Args:
            table_name: 表名

        Returns:
            bool: 如果表存在则返回True，否则返回False
        """
        raise NotImplementedError("子类必须实现 check_table_exists 方法")

    @abstractmethod
    async def query_single_step_graph_by_node(self, node_uuid: str):
        """
        根据节点 UUID 查询图数据库中的节点，并返回其对应 Pydantic 模型实例。
        """
        raise NotImplementedError("子类必须实现 query_single_step_graph_by_node 方法")