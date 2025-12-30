import pytest
from src.common.config.db import db_rel, async_cache, db_vector, db_graph
from sqlmodel import Column, DateTime, Field, SQLModel
from pydantic import BaseModel
from datetime import datetime, timezone
from uuid import uuid4
import logging
import networkx as nx

# import numpy as np

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_db_rel_connection():
    """test db_rel connection"""
    logger.info("test db_rel connection start")
    try:

        class TestRelBase(SQLModel, table=True):
            id: str = Field(
                default_factory=lambda: uuid4().hex,
                primary_key=True,  # 主键
                index=True,  # 索引
                description="唯一标识符",
            )
            value: int = Field(default=0, description="数值字段")
            created_at: datetime = Field(
                default_factory=lambda: datetime.now(timezone.utc),
                sa_column=Column(DateTime(timezone=True)),
                description="创建时间",
            )

        await db_rel.create_all()
        # 插入一条数据
        test_rel_base = TestRelBase(value=1)
        async with db_rel.session_factory() as session:
            async with session.begin():
                session.add(test_rel_base)
                # 提交事务以触发数据库生成 ID
                await session.flush()
        async with db_rel.session_factory() as session:
            async with session.begin():
                # 检查数据是否插入成功
                test_rel_base_result = await session.get(TestRelBase, test_rel_base.id)
                assert test_rel_base_result.value == test_rel_base.value, (
                    "expect inserted data"
                )
        logger.info("db_rel connection and insert data success")
    except Exception as e:
        logger.error(f"db_rel connection fail: {e}")
        pytest.fail(f"db_rel connection fail: {e}")


@pytest.mark.asyncio
async def test_db_cache_connection():
    """test db_cache connection"""
    logger.info("test db_cache connection start")
    try:
        await async_cache.ping()
        logger.info("db_cache connection success")
        logger.info("test db_cache set get operation start")
        try:
            await async_cache.set("sys_test", "1")
            value = (await async_cache.get("sys_test")).decode("utf-8")
            assert value == "1", f"expect '1', but got '{value}'"
            logger.info(f"db_cache set get operation success: {value}")
        except Exception as e:
            logger.error(f"db_cache set get operation fail: {e}")
            pytest.fail(f"db_cache set get operation fail: {e}")
    except Exception as e:
        logger.error(f"db_cache connection fail: {e}")
        pytest.fail(f"db_cache connection fail: {e}")


@pytest.mark.asyncio
async def test_db_vector_connection():
    """test db_vector connection"""
    logger.info("test db_vector connection start")
    try:
        await db_vector.connect()
        logger.info("db_vector connection success")

        class TestVectorBase(BaseModel):
            id: str = Field(
                default_factory=lambda: uuid4().hex,
                primary_key=True,  # 主键
                index=True,  # 索引
                description="唯一标识符",
            )
            vector: list[float] | None = Field(
                default_factory=lambda: [0.1] * 1024, description="向量字段"
            )

        await db_vector.create_table(TestVectorBase, {"vector": 1024})
        logger.info("db_vector create table success")
        await db_vector.add([TestVectorBase(id="test", vector=[0.1] * 1024)])
        result = await db_vector.search(TestVectorBase, [0.1] * 1024)
        assert result[0].id == "test", f"expect 'test', but got '{result[0].id}'"
        logger.info(f"db_vector query operation success: {result[0].id}")

    except Exception as e:
        logger.error(f"db_vector connection fail: {e}")
        pytest.fail(f"db_vector connection fail: {e}")


@pytest.mark.asyncio
async def test_db_graph_connection():
    """test db_graph connection"""
    logger.info("test db_graph connection start")
    try:
        db_graph.connect()
        await db_graph.drop_tables_all()
        assert await db_graph.list_tables() == [], "expect empty list"

        class TestGraphNodeCity(BaseModel):
            uuid: str = Field(
                default_factory=lambda: uuid4().hex,
                primary_key=True,  # 主键
                index=True,  # 索引
                description="唯一标识符",
            )
            name: str = Field(default="", description="城市名称")

        class TestGraphNodeUser(BaseModel):
            uuid: str = Field(
                default_factory=lambda: uuid4().hex,
                primary_key=True,  # 主键
                index=True,  # 索引
                description="唯一标识符",
            )
            name: str = Field(default="", description="用户名称")
            age: int = Field(default=0, description="用户年龄")

        class TestGraphEdgeFollows(BaseModel):
            uuid: str = Field(
                default_factory=lambda: uuid4().hex,
                primary_key=True,  # 主键
                index=True,  # 索引
                description="唯一标识符",
            )
            source: TestGraphNodeUser = Field(default="", description="源节点ID")
            target: TestGraphNodeUser = Field(default="", description="目标节点ID")

        class TestGraphEdgeLivesIn(BaseModel):
            uuid: str = Field(
                default_factory=lambda: uuid4().hex,
                primary_key=True,  # 主键
                index=True,  # 索引
                description="唯一标识符",
            )
            source: TestGraphNodeUser = Field(default="", description="源节点ID")
            target: TestGraphNodeCity = Field(default="", description="目标节点ID")
            weight: float = Field(default=0.0, description="边权重")

        node_city_dalian = TestGraphNodeCity(uuid="dalian", name=" Dalian")
        node_user_zhangsan = TestGraphNodeUser(
            uuid="zhangsan", name=" Zhangsan", age=18
        )
        node_user_lisi = TestGraphNodeUser(uuid="lisi", name=" Lisi", age=20)
        edge_lives_in_zhangsan_dalian = TestGraphEdgeLivesIn(
            source=node_user_zhangsan, target=node_city_dalian, weight=0.5
        )
        edge_follows_zhangsan_lisi = TestGraphEdgeFollows(
            source=node_user_zhangsan, target=node_user_lisi
        )

        # # 插入三个节点两个边,都带属性字段
        # G = nx.Graph()
        # G.add_node(1, label="A", type="node")
        # G.add_edge(2, 3, weight=0.7)
        # 插入图
        # await db_graph.async_graph.add_graph(G)

        # 创建表
        await db_graph.create_table_node(TestGraphNodeCity)
        await db_graph.create_table_node(TestGraphNodeUser)
        await db_graph.create_table_edge(TestGraphEdgeFollows)
        await db_graph.create_table_edge(TestGraphEdgeLivesIn)

        # 添加数据
        await db_graph.add_node(node_city_dalian)
        await db_graph.add_node(node_user_zhangsan)
        await db_graph.add_node(node_user_lisi)
        await db_graph.add_edge(edge_lives_in_zhangsan_dalian)
        await db_graph.add_edge(edge_follows_zhangsan_lisi)

        # 检查表是否存在
        assert await db_graph.check_table_exists(TestGraphNodeCity.__name__.lower()), (
            "TestGraphNodeCity table should exist"
        )
        assert await db_graph.check_table_exists(
            TestGraphEdgeLivesIn.__name__.lower()
        ), "TestGraphEdgeLivesIn table should exist"

        # 查找数据
        result = await db_graph.query_node_by_uuid(TestGraphNodeCity, "dalian")
        assert result.uuid == "dalian", f"expect 'dalian', but got '{result.uuid}'"
        # 查找关联数据
        result = await db_graph.query_single_step_graph_by_node(node_user_zhangsan.uuid)
        assert result[0]["edge"]["uuid"] in [
            edge_lives_in_zhangsan_dalian.uuid,
            edge_follows_zhangsan_lisi.uuid,
        ], (
            f"""expect '{edge_lives_in_zhangsan_dalian.uuid}' or '{edge_follows_zhangsan_lisi.uuid}', but got '{result[0]["edge"]["uuid"]}'"""
        )
        assert result[0]["node"]["uuid"] in [
            node_city_dalian.uuid,
            node_user_lisi.uuid,
        ], (
            f"expect '{node_city_dalian.uuid}' or '{node_user_lisi.uuid}', but got '{result[0]['node']['uuid']}'"
        )

        logger.info("db_graph connection success")
    except Exception as e:
        logger.error(f"db_graph connection fail: {e}")
        pytest.fail(f"db_graph connection fail: {e}")
