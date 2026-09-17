
from common.config.server import app
from module_main.service.db import TableService
from module_main.service.db_meta import DbMetaService

# lib
from fastapi import APIRouter, status
import logging
logger = logging.getLogger(__name__)
# 基础db
router = APIRouter()


# 测试
@router.get(
    "/create", summary="创建表", status_code=status.HTTP_201_CREATED
)
async def create():
    """
    创建所有未创建的数据库表

    返回:
        HTTPException: 成功返回200状态码，失败返回500状态码
    """
    result = await TableService.create()
    return result


# 更新数据库
@router.get("/reset", summary="重置表", status_code=status.HTTP_201_CREATED)
async def reset():
    """
    更新所有数据库表

    返回:
        HTTPException: 成功返回200状态码，失败返回500状态码
    """
    result = await TableService.reset()
    return result


# 数据表清单(只读)
@router.get("/tables", summary="数据表清单")
async def tables(keyword: str | None = None):
    """
    列出关系库数据表及数据量/最近更新时间

    Args:
        keyword: 按表名/注释关键字过滤

    Returns:
        list[dict]: name/comment/column_count/row_count/last_updated
    """
    return await DbMetaService.tables(keyword)


# 向量库表清单(只读)
@router.get("/vector", summary="向量库表清单")
async def vector_tables():
    """
    列出向量库表及字段数/向量维度/数据条数

    Returns:
        dict: {type, tables}
    """
    return await DbMetaService.vector_tables()


# 缓存数据库信息(只读)
@router.get("/cache", summary="缓存数据库信息")
async def cache_info():
    """
    Redis 缓存运行信息(键数量/内存/命中率/版本等)

    Returns:
        dict: 缓存概要信息
    """
    return await DbMetaService.cache_info()


# 图数据库信息(只读)
@router.get("/graph", summary="图数据库信息")
async def graph_info():
    """
    图数据库运行信息(类型/连接状态/地址等)

    Returns:
        dict: 图库信息
    """
    return await DbMetaService.graph_info()


app.include_router(router, prefix="/db", tags=["db"])
logger.info("ok...controller_index")
