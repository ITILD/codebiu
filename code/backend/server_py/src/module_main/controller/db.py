
from common.config.server import app
from module_main.service.db import TableService

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


app.include_router(router, prefix="/db", tags=["db"])
logger.info("ok...controller_index")
