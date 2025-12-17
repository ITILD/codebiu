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
        await db_graph.connect()
        # 插入三个节点两个边,都带属性字段
        G = nx.Graph()
        G.add_node(1, label="A", type="node")
        G.add_node(2, label="B", type="node")
        G.add_node(3, label="C", type="node")
        G.add_edge(1, 2, weight=0.5)
        G.add_edge(2, 3, weight=0.7)
        # 插入图
        await db_graph.async_graph.add_graph(G)
        
        
        logger.info("db_graph connection success")
    except Exception as e:
        logger.error(f"db_graph connection fail: {e}")
        pytest.fail(f"db_graph connection fail: {e}")
