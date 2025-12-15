import pytest
from src.common.config.db import db_rel, async_cache,db_vector
from sqlmodel import Column, DateTime, Field, SQLModel
from datetime import datetime, timezone
from uuid import uuid4
import logging

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
                assert test_rel_base_result.value == test_rel_base.value, "expect inserted data"
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
        # TODO 动态类型 后续支持pgvector
        # class Content(LanceModel): 
        #     id: int
        #     vector: Vector(128)

                
    except Exception as e:
        logger.error(f"db_vector connection fail: {e}")
        pytest.fail(f"db_vector connection fail: {e}")
