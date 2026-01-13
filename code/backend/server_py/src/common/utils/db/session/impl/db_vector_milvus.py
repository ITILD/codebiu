from pydantic import BaseModel, Field
from pymilvus import (
    AsyncMilvusClient,
    DataType,
    CollectionSchema,
    FieldSchema,
)
from common.utils.db.do.db_config import MilvusConfig
from common.utils.db.session.interface.db_vector_interface import DBVectorInterface
from bidict import bidict
import logging

logger = logging.getLogger(__name__)


class VectorBase(BaseModel):
    """向量基类"""

    content_vec: list[float]


class DBVectorMilvus(DBVectorInterface):
    """
    Milvus向量数据库实现
    封装向量数据库操作
    """

    # 类型转换映射 双向dict
    py2sql_type_bidict: bidict = bidict(
        {
            "bool": DataType.BOOL,
            "int": DataType.INT64,
            "float": DataType.DOUBLE,
            "str": DataType.VARCHAR,
            "datetime": DataType.TIMESTAMPTZ,  # Milvus中用整数表示时间戳
            "list": DataType.ARRAY,  # Milvus中用JSON表示复杂类型
            "dict": DataType.JSON,  # Milvus中用JSON表示复杂类型
        }
    )

    def __init__(self, milvus_config: MilvusConfig):
        """
        初始化Milvus向量数据库连接

        Args:
            milvus_config: Milvus数据库配置对象
        """
        self.milvus_config = milvus_config
        self.async_vector = None

    async def connect(self, log_bool=False):
        """
        建立数据库连接

        Args:
            log_bool: 是否启用日志
        """
        try:
            # 创建Milvus客户端实例
            if self.milvus_config.token:
                self.async_vector = AsyncMilvusClient(
                    uri=f"{self.milvus_config.host}:{self.milvus_config.port}",
                    token=self.milvus_config.token,
                )
            elif self.milvus_config.user and self.milvus_config.password:
                self.async_vector = AsyncMilvusClient(
                    uri=f"{self.milvus_config.host}:{self.milvus_config.port}",
                    user=self.milvus_config.user,
                    password=self.milvus_config.password,
                )
            else:
                self.async_vector = AsyncMilvusClient(
                    uri=f"{self.milvus_config.host}:{self.milvus_config.port}"
                )

            if log_bool:
                logger.info(
                    f"Milvus数据库连接成功: {self.milvus_config.host}:{self.milvus_config.port}"
                )
        except Exception as e:
            raise Exception(f"Milvus数据库连接失败: {e}")

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

    async def create_table(
        self,
        schema_cls: type[BaseModel],
        vector_dims: dict[str, int] = {"vector": 1024},
    ):
        """
        创建 Milvus 集合（Collection）结构

        Args:
            schema_cls: 原始 Pydantic 模型类（BaseModel 子类）
            vector_dims: 向量字段名 -> 维度 的映射
        """
        try:
            collection_name = schema_cls.__name__.lower()

            # 检查集合是否已存在，如果存在则删除 TODO 旧表备份
            if await self.async_vector.has_collection(collection_name):
                await self.async_vector.drop_collection(collection_name)

            # 构建字段模式
            fields = []
            for field_name, field_info in schema_cls.model_fields.items():
                if field_name in vector_dims:
                    # 向量字段
                    fields.append(
                        FieldSchema(
                            field_name,
                            DataType.FLOAT_VECTOR,
                            dim=vector_dims[field_name],
                        )
                    )
                else:
                    # 其他字段 - 使用类型转换方法
                    sql_type, _ = await self._convert_py_type_to_sql_type(
                        field_info.annotation.__name__, None
                    )
                    # 默认处理为字符串类型 TODO 其他限制校验字段
                    fields.append(FieldSchema(field_name, sql_type))
            # 创建集合模式
            schema = CollectionSchema(
                fields, description=f"Schema for {collection_name}"
            )

            # 创建集合
            await self.async_vector.create_collection(collection_name, schema=schema)

        except Exception as e:
            raise Exception(f"Milvus创建集合失败: {e}") from e

    # async def create_index(
    #     self,
    #     schema_cls: type[BaseModel],
    #     vector_dims: dict[str, int] = {"vector": 1024},
    # ):
    #     try:
    #         collection_name = schema_cls.__name__.lower()
    #         # 创建索引以提高搜索性能
    #         index_params = AsyncMilvusClient.prepare_index_params()
    #         for field_name, field_info in schema_cls.model_fields.items():
    #             if field_name in vector_dims:
    #                 # 每个需要建立索引的向量字段 TODO 普通字段  或者严格按index设置
    #                 index_params.add_index(
    #                     field_name=f"{collection_name}_{field_name}_index",  # Name of the vector field to be indexed
    #                     index_type="HNSW",  # Type of the index to create
    #                     index_name="vector_index",  # Name of the index to create
    #                     metric_type="COSINE",  # Metric type used to measure similarity
    #                     params={
    #                         "M": 64,  # Maximum number of neighbors each node can connect to in the graph
    #                         "efConstruction": 100,  # Number of candidate neighbors considered for connection during index construction
    #                     },  # Index building params
    #                 )
    #         await self.async_vector.create_index(
    #             collection_name, "vector", index_params
    #         )
    #     except Exception as e:
    #         raise Exception(f"Milvus创建索引失败: {e}") from e

    async def add(
        self,
        data_list_class: list[BaseModel],
    ) -> None:
        """
        向 Milvus 集合中添加数据。

        Args:
            data_list_class: 要添加的数据列表
        """
        if not data_list_class:
            return

        collection_name = data_list_class[0].__class__.__name__.lower()

        # 将数据转换为字典列表
        data_list_dict = []
        for item in data_list_class:
            item_dict = item.model_dump()
            data_list_dict.append(item_dict)

        # 插入数据到Milvus
        await self.async_vector.insert(collection_name, data_list_dict)

    async def search(
        self,
        schema_cls: type[BaseModel],
        query_vector: list[float],
        top_k: int = 5,
    ) -> list[type[BaseModel]]:
        """
        查询 Milvus 集合中与查询向量最相似的记录。

        Args:
            schema_cls: 原始 Pydantic 模型类（BaseModel 子类）
            query_vector: 查询向量
            top_k: 返回的最相似结果数量，默认为5
        """
        collection_name = schema_cls.__name__.lower()

        # 执行搜索
        search_params = {
            "metric_type": "COSINE",  # 或者使用 "L2", "IP" 等
            "params": {"nprobe": 10},
        }

        results = await self.async_vector.search(
            collection_name,
            [query_vector],  # Milvus期望批次格式
            "vector",  # 向量字段名
            search_params,
            limit=top_k,
            output_fields=list(schema_cls.model_fields.keys()),  # 返回所有字段
        )

        # 解析结果
        result_items = []
        for hits in results:
            for hit in hits:
                # 构造结果对象
                result_data = {
                    field: hit.entity.get(field)
                    for field in schema_cls.model_fields.keys()
                }
                result_item = schema_cls.model_validate(result_data)
                result_items.append(result_item)

        return result_items

    async def is_connected(self):
        """
        检查连接状态

        Returns:
            bool: 如果连接有效则返回True，否则返回False
        """
        if not self.async_vector:
            return False
        try:
            # 尝试获取数据库连接状态
            await self.async_vector.list_collections()
            return True
        except Exception:
            return False

    async def disconnect(self):
        """
        断开数据库连接
        """
        if self.async_vector:
            # 关闭Milvus连接
            await self.async_vector.close()

    async def reconnect(self):
        """
        重新连接数据库
        """
        await self.disconnect()
        await self.connect()

    async def create_all(self):
        """创建所有表结构"""
        pass
