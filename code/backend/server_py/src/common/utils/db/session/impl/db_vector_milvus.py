from pydantic import BaseModel
from pymilvus import AsyncMilvusClient, DataType, CollectionSchema, FieldSchema, connections
from common.utils.db.do.db_config import MilvusConfig
from common.utils.db.session.interface.db_vector_interface import DBVectorInterface


class VectorBase(BaseModel):
    """向量基类"""
    content_vec: DataType.FLOAT_VECTOR = FieldSchema(
        name="content_vec",
        dtype=DataType.FLOAT_VECTOR,
        dim=1024,
        description="向量字段",
    )

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

    async def create_all(self):
        """创建所有表结构"""
        pass