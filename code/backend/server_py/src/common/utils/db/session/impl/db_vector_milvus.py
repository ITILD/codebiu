from pydantic import BaseModel
from pymilvus import (
    AsyncMilvusClient,
    DataType,
    CollectionSchema,
    FieldSchema,
    Collection
)
from pymilvus import Function, FunctionType
from pydantic_core import PydanticUndefined
from common.utils.db.do.db_config import MilvusConfig
from common.utils.db.orm.vector_model import VectorModel
from common.utils.db.session.interface.db_vector_interface import DBVectorInterface
from bidict import bidict
from annotated_types import MaxLen
import json
import logging
logger = logging.getLogger(__name__)



class VectorBase(BaseModel):
    """向量基类"""

    content_vec: list[float]


class DBVectorMilvus(DBVectorInterface):
    """
    Milvus向量数据库实现
    封装向量数据库操作
    注:单表必须有主键 且str字段必须要有max_length
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
        self.async_vector = AsyncMilvusClient | None


    async def connect(self, log_bool=False):
        """
        建立数据库连接

        Args:
            log_bool: 是否启用日志
        """
        try:
            # 创建Milvus客户端实例
            uri = self.milvus_config.uri or f"{self.milvus_config.host}:{self.milvus_config.port}"

            if self.milvus_config.token:
                self.async_vector = AsyncMilvusClient(
                    uri=uri,
                    token=self.milvus_config.token,
                )
            elif self.milvus_config.user and self.milvus_config.password:
                self.async_vector = AsyncMilvusClient(
                    uri=uri,
                    user=self.milvus_config.user,
                    password=self.milvus_config.password,
                )
            else:
                self.async_vector = AsyncMilvusClient(uri=uri)

            if log_bool:
                logger.info(
                    f"Milvus数据库连接成功: {self.milvus_config.host}:{self.milvus_config.port}"
                )
        except Exception as e:
            raise Exception(f"Milvus数据库连接失败: {e}")

    async def _convert_py_type_to_sql_type(self, py_type: str, data: object) -> tuple[str, object]:
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
            logger.warning(f"未定义 Python 类型 {py_type!r} 的 SQL 映射，默认使用 STRING")
            return DataType.VARCHAR, str(data)
        return sql_type, data

    async def create_table(
        self,
        schema_cls: type[BaseModel],
        vector_dims: dict[str, int] = {"vector": 1024},
    ):
        """
        创建 Milvus 集合（Collection）结构
        """
        try:
            collection_name = schema_cls.__name__.lower()

            # # 检查集合是否已存在，如果存在则log警告
            if await self.async_vector.has_collection(collection_name):
                logger.warning(f"集合 {collection_name} 已存在")
                return

            # 构建字段模式
            fields = []
            primary_field_name = None
            analyzer_field_name = None
            sparse_field_name = None

            for field_name, field_info in schema_cls.model_fields.items():
                # 安全获取 primary_key (完美兼容 Pydantic V2)
                is_primary = False
                if hasattr(field_info, "json_schema_extra") and isinstance(
                    field_info.json_schema_extra, dict
                ):
                    is_primary = field_info.json_schema_extra.get("primary_key", False)
                # 兜底：兼容某些旧版本或特殊配置直接挂在 field_info 上的情况
                elif hasattr(field_info, "primary_key"):
                    # 注意: sqlmodel FieldInfo 的 primary_key 默认值是 PydanticUndefined(truthy),
                    # 直接 getattr 会把未声明主键的字段误判为主键, 必须显式排除
                    _pk_val = getattr(field_info, "primary_key", False)
                    is_primary = bool(_pk_val) and _pk_val is not PydanticUndefined
                # 必须有且仅有一个主键
                if is_primary:
                    if primary_field_name is not None:
                        raise ValueError("Only one primary key is allowed.")
                    primary_field_name = field_name

                # 优先检查是否有显式的 Milvus 数据类型覆盖
                milvus_dtype_override = None
                if hasattr(field_info, "json_schema_extra") and isinstance(
                    field_info.json_schema_extra, dict
                ):
                    milvus_dtype_override = field_info.json_schema_extra.get("milvus_dtype")

                if field_name in vector_dims:
                    # 向量字段
                    fields.append(
                        FieldSchema(
                            field_name,
                            DataType.FLOAT_VECTOR,
                            dim=vector_dims[field_name],
                        )
                    )
                elif milvus_dtype_override == "SPARSE_FLOAT_VECTOR":
                    # 显式识别为稀疏向量
                    sql_type = DataType.SPARSE_FLOAT_VECTOR
                    sparse_field_name = field_name
                    fields.append(FieldSchema(name=field_name, dtype=sql_type))

                elif milvus_dtype_override == "JSON":
                    # 显式识别为 JSON 字段（用于 BaseModel/dict 等复杂类型）
                    fields.append(
                        FieldSchema(
                            name=field_name,
                            dtype=DataType.JSON,
                            is_primary=is_primary,
                        )
                    )

                else:
                    # 其他字段 - 使用类型转换方法
                    # 安全获取类型名称，防止遇到 list[float] 等泛型时报错
                    type_name = getattr(
                        field_info.annotation, "__name__", str(field_info.annotation)
                    )
                    sql_type, _ = await self._convert_py_type_to_sql_type(type_name, None)

                    # ARRAY 字段需指定元素类型；元素为复杂类型(枚举/模型等不在
                    # py2sql_type_bidict 的)时回退到 VARCHAR(JSON) 存储
                    element_type = None
                    if sql_type == DataType.ARRAY:
                        args = getattr(field_info.annotation, "__args__", ())
                        elem_name = (
                            getattr(args[0], "__name__", str(args[0]))
                            if args
                            else None
                        )
                        if elem_name and elem_name in self.py2sql_type_bidict:
                            element_type = self.py2sql_type_bidict[elem_name]
                        else:
                            sql_type = DataType.VARCHAR

                    if sql_type == DataType.VARCHAR:
                        max_length = 255
                        enable_analyzer = False
                        analyzer_params = None  # 默认为 None

                        if hasattr(field_info, "json_schema_extra") and isinstance(
                            field_info.json_schema_extra, dict
                        ):
                            max_length = field_info.json_schema_extra.get("max_length", 255)
                            enable_analyzer = field_info.json_schema_extra.get(
                                "enable_analyzer", False
                            )

                            # 优先读取 multi_analyzer_params，如果没有则读取普通的 analyzer_params
                            multi_params = field_info.json_schema_extra.get("multi_analyzer_params")
                            if multi_params:
                                analyzer_params = (
                                    json.dumps(multi_params)
                                    if isinstance(multi_params, dict)
                                    else multi_params
                                )
                            else:
                                simple_params = field_info.json_schema_extra.get("analyzer_params")
                                if simple_params:
                                    analyzer_params = (
                                        json.dumps(simple_params)
                                        if isinstance(simple_params, dict)
                                        else simple_params
                                    )

                        for meta in field_info.metadata:
                            if isinstance(meta, MaxLen):
                                max_length = meta.max_length  # 覆盖之前的值
                                break

                        field_this = FieldSchema(
                            name=field_name,
                            dtype=sql_type,
                            is_primary=is_primary,
                            max_length=max_length,
                            enable_analyzer=enable_analyzer,
                            analyzer_params=analyzer_params,  # 传入 JSON 字符串格式的 analyzer 配置
                        )

                        if enable_analyzer:
                            analyzer_field_name = field_name
                    elif sql_type == DataType.SPARSE_FLOAT_VECTOR:  # 【关键】识别稀疏向量字段
                        sparse_field_name = field_name
                        field_this = FieldSchema(name=field_name, dtype=sql_type)
                    else:
                        if sql_type == DataType.ARRAY and element_type is not None:
                            field_kwargs = {
                                "name": field_name,
                                "dtype": sql_type,
                                "is_primary": is_primary,
                                "element_type": element_type,
                            }
                            # ARRAY<VARCHAR> 需指定元素 max_length
                            if element_type == DataType.VARCHAR:
                                field_kwargs["max_length"] = 255
                            # ARRAY 字段需指定最大元素数
                            field_kwargs["max_capacity"] = 64
                            field_this = FieldSchema(**field_kwargs)
                        else:
                            field_this = FieldSchema(
                                name=field_name, dtype=sql_type, is_primary=is_primary
                            )

                    fields.append(field_this)

            # 如果同时存在 analyzer 字段和 sparse 字段，自动创建 BM25 Function
            bm25_function = None
            if analyzer_field_name and sparse_field_name:
                bm25_function = Function(
                    name=f"bm25_{analyzer_field_name}_to_{sparse_field_name}",
                    function_type=FunctionType.BM25,
                    input_field_names=[analyzer_field_name],
                    output_field_names=[sparse_field_name],
                )
            # 注意：CollectionSchema 的 functions 参数在 pymilvus 中接受列表,
            # 无 BM25 函数时必须传 None(传 [None] 会触发 SchemaNotReadyException)
            schema = CollectionSchema(
                fields,
                description=f"Schema for {collection_name}",
                functions=[bm25_function] if bm25_function else None,
            )
            # 创建集合
            await self.async_vector.create_collection(collection_name, schema=schema)

            # 创建索引
            await self.create_index(schema_cls, vector_dims)

            # 为稀疏向量字段创建专属索引
            if sparse_field_name:
                # 实例化 IndexParams 对象
                sparse_index_params = self.async_vector.prepare_index_params()
                # 使用 add_index 方法添加稀疏向量索引配置
                sparse_index_params.add_index(
                    field_name=sparse_field_name,
                    index_type="SPARSE_INVERTED_INDEX",  # 稀疏向量专用的倒排索引
                    metric_type="BM25",  # 稀疏向量使用内积 (Inner Product)
                )

                await self.async_vector.create_index(
                    collection_name=collection_name, index_params=sparse_index_params
                )
                logger.info(
                    f"已为稀疏向量字段 '{sparse_field_name}' 创建 SPARSE_INVERTED_INDEX 索引"
                )

            # load collection
            await self.async_vector.load_collection(collection_name)
            logger.info(f"Milvus 集合 {collection_name} 创建并加载成功！")
        except Exception as e:
            raise Exception(f"Milvus创建集合失败: {e}") from e

    async def create_index(
        self,
        schema_cls: type[BaseModel],
        vector_dims: dict[str, int] = {"vector": 1024},
    ):
        try:
            collection_name = schema_cls.__name__.lower()
            # 创建索引以提高搜索性能
            index_params = AsyncMilvusClient.prepare_index_params()
            for field_name, field_info in schema_cls.model_fields.items():
                if field_name in vector_dims:
                    # 每个需要建立索引的向量字段 TODO 普通字段  或者严格按index设置
                    index_params.add_index(
                        field_name=field_name,  # Name of the vector field to be indexed
                        index_type="HNSW",  # Type of the index to create
                        index_name=f"{collection_name}_{field_name}_index",  # Name of the index to create
                        metric_type="COSINE",  # Metric type used to measure similarity
                        params={
                            "M": 64,  # Maximum number of neighbors each node can connect to in the graph
                            "efConstruction": 100,  # Number of candidate neighbors considered for connection during index construction
                        },  # Index building params
                    )
            await self.async_vector.create_index(collection_name, index_params)
        except Exception as e:
            raise Exception(f"Milvus创建索引失败: {e}") from e

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

        # 预扫描 JSON 类型字段，None 值会触发 pymilvus 跳过该行导致 num_rows 不一致
        json_fields: set[str] = set()
        for fname, finfo in data_list_class[0].__class__.model_fields.items():
            if (
                isinstance(finfo.json_schema_extra, dict)
                and finfo.json_schema_extra.get("milvus_dtype") == "JSON"
            ):
                json_fields.add(fname)

        # 将数据转换为字典列表
        data_list_dict = []
        for item in data_list_class:
            item_dict = item.model_dump()
            for fname in json_fields:
                if item_dict.get(fname) is None:
                    item_dict[fname] = {}
            data_list_dict.append(item_dict)

        # 插入数据到Milvus
        await self.async_vector.insert(collection_name, data_list_dict)

    async def search(
        self,
        schema_cls: type[BaseModel],
        query_vector: list[float],
        vector_dims_key: str = "vector",
        limit: int = 5,
    ) -> list[type[BaseModel]]:
        """
        查询 Milvus 集合中与查询向量最相似的记录。

        Args:
            schema_cls: 原始 Pydantic 模型类（BaseModel 子类）
            query_vector: 查询向量
            limit: 返回的最相似结果数量，默认为5
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
            # filter
            limit=limit,
            output_fields=list(schema_cls.model_fields.keys()),  # 返回所有字段
            search_params=search_params,
            anns_field=vector_dims_key,
        )

        # 解析结果
        result_items = []
        for hits in results:
            for hit in hits:
                # 构造结果对象
                result_data = {
                    field: hit.entity.get(field) for field in schema_cls.model_fields.keys()
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

    async def delete_by_ids(self, schema_cls: type[BaseModel], ids: list[str]):
        """根据ID删除数据"""
        collection_name = schema_cls.__name__.lower()
        await self.async_vector.delete(
            collection_name,
            ids=ids,
        )
        await self.async_vector.flush(collection_name)


    async def load_all(self):
        """加载所有集合"""
        await self.async_vector.list_collections()
        for collection_name in await self.async_vector.list_collections():
            await self.async_vector.load_collection(collection_name)

    
    async def create_all(self):
        """创建所有已注册但未存在的向量表结构"""
        # 一次性获取已存在的集合名,避免每个表重复探测
        existing = set(await self.async_vector.list_collections())
        for table_name, schema_cls in VectorModel.registry.items():
            if table_name in existing:
                logger.info(f"向量表 {table_name} 已存在,跳过")
                continue
            # 从模型自动提取 vector_dim 字段(如 embedding=1024),无需手动传参
            vector_dims = schema_cls.vector_dims()
            await self.create_table(schema_cls, vector_dims)
            logger.info(f"已创建向量表 {table_name}")
    
