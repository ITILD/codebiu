from pymilvus import AsyncMilvusClient, DataType, CollectionSchema, FieldSchema, connections
from common.utils.db.do.db_config import MilvusLiteConfig
from common.utils.db.session.interface.db_vector_interface import DBVectorInterface
from pathlib import Path

class DBVectorMilvusLite(DBVectorInterface):
    """
    Milvus Lite向量数据库实现
    封装向量数据库操作
    """
    database:str = None
    async_client:AsyncMilvusClient = None

    def __init__(self, milvus_config: MilvusLiteConfig):
        """
        初始化Milvus Lite向量数据库连接

        Args:
            milvus_config: Milvus Lite数据库配置对象
        """
        self.database = Path(milvus_config.database).absolute().as_posix()

    async def connect(self, log_bool=False):
        """
        建立数据库连接

        Args:
            log_bool: 是否启用日志
        """
        try:
            # 创建Milvus客户端实例
            self.async_client = AsyncMilvusClient(self.database)

            if log_bool:
                print(f"Milvus Lite数据库连接成功: {self.database}")
        except Exception as e:
            raise Exception(f"Milvus Lite数据库连接失败: {e}")

    async def is_connected(self):
        """
        检查连接状态

        Returns:
            bool: 如果连接有效则返回True，否则返回False
        """
        if not self.client:
            return False
        try:
            # 尝试获取数据库信息
            await self.client.describe_collection(
                collection_name=self.milvus_config.collection_name
            )
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
            # MilvusClient不需要显式关闭连接
            self.client = None

    async def get_info(self):
        """
        获取数据库信息

        Returns:
            dict: 包含数据库信息的字典
        """
        connected = await self.is_connected()
        return {
            "type": "Milvus Lite",
            "database": self.milvus_config.database,
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
