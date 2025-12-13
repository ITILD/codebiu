from pymilvus import AsyncMilvusClient, DataType, CollectionSchema, FieldSchema, connections
from common.utils.db.do.db_config import MilvusConfig
from common.utils.db.session.interface.db_vector_interface import DBVectorInterface


class DBVectorMilvus(DBVectorInterface):
    """
    Milvus向量数据库实现
    封装向量数据库操作
    """

    def __init__(self, milvus_config: MilvusConfig):
        """
        初始化Milvus向量数据库连接

        Args:
            milvus_config: Milvus数据库配置对象
        """
        self.milvus_config = milvus_config
        self.async_client  = None

    def connect(self, log_bool=False):
        """
        建立数据库连接

        Args:
            log_bool: 是否启用日志
        """
        try:
            # 连接到Milvus服务器
            connections.connect(
                alias="default",
                host=self.milvus_config.host,
                port=self.milvus_config.port,
            )

            # 创建Milvus客户端实例
            self.client = AsyncMilvusClient(
                uri=f"http://{self.milvus_config.host}:{self.milvus_config.port}"
            )

            if log_bool:
                print(
                    f"Milvus数据库连接成功: {self.milvus_config.host}:{self.milvus_config.port}"
                )
        except Exception as e:
            raise Exception(f"Milvus数据库连接失败: {e}")

    async def is_connected(self):
        """
        检查连接状态

        Returns:
            bool: 如果连接有效则返回True，否则返回False
        """
        if not self.client:
            return False
        try:
            # 尝试获取数据库连接状态
            await self.client.list_collections()
            return True
        except Exception:
            return False

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
        if self.client:
            # 断开连接
            connections.disconnect("default")
            self.client = None

    async def get_info(self):
        """
        获取数据库信息

        Returns:
            dict: 包含数据库信息的字典
        """
        connected = await self.is_connected()
        return {
            "type": "Milvus",
            "host": self.milvus_config.host,
            "port": self.milvus_config.port,
            "collection_name": self.milvus_config.collection_name,
            "connected": connected,
        }

    async def create_collection(self, collection_name: str, schema: CollectionSchema = None):
        """
        创建集合

        Args:
            collection_name: 集合名称
            schema: 集合模式定义
        """
        if not self.client:
            raise Exception("数据库未连接")

        try:
            if schema:
                await self.client.create_collection(
                    collection_name=collection_name, schema=schema
                )
            else:
                # 如果没有提供模式，则创建一个默认的向量集合
                # 定义字段
                id_field = FieldSchema(
                    name="id", dtype=DataType.INT64, is_primary=True, auto_id=True
                )
                vector_field = FieldSchema(
                    name="embedding", dtype=DataType.FLOAT_VECTOR, dim=128
                )

                # 创建模式
                schema = CollectionSchema(
                    fields=[id_field, vector_field], description="向量集合"
                )
                await self.client.create_collection(
                    collection_name=collection_name, schema=schema
                )
        except Exception as e:
            raise Exception(f"创建集合失败: {e}")

    async def insert_vectors(
        self, collection_name: str, vectors: list, metadata: list = None
    ):
        """
        插入向量数据

        Args:
            collection_name: 集合名称
            vectors: 向量数据列表
            metadata: 元数据列表

        Returns:
            插入结果
        """
        if not self.client:
            raise Exception("数据库未连接")

        try:
            # 准备数据
            data = []
            for i, vector in enumerate(vectors):
                record = {"embedding": vector}
                if metadata and i < len(metadata):
                    record.update(metadata[i])
                data.append(record)

            # 插入数据
            result = await self.client.insert(collection_name=collection_name, data=data)
            return result
        except Exception as e:
            raise Exception(f"插入向量数据失败: {e}")

    async def search_vectors(
        self, collection_name: str, query_vectors: list, limit: int = 10
    ):
        """
        搜索相似向量

        Args:
            collection_name: 集合名称
            query_vectors: 查询向量列表
            limit: 返回结果数量限制

        Returns:
            搜索结果
        """
        if not self.client:
            raise Exception("数据库未连接")

        try:
            # 执行搜索
            result = await self.client.search(
                collection_name=collection_name,
                data=query_vectors,
                limit=limit,
                output_fields=["id"],
            )
            return result
        except Exception as e:
            raise Exception(f"向量搜索失败: {e}")
