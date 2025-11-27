
from common.config.server import app
from fastapi import Depends, status, HTTPException, APIRouter
from fastapi.responses import StreamingResponse
from module_main.dependencies.index import get_index_service
from module_main.service.index import IndexService

# 流式返回GET接口示例
@app.get("/stream_get")
async def stream_get(index_service: IndexService = Depends(get_index_service)):
    """
    流式返回GET请求数据
    """
    stream_generator = index_service.stream_get()
    return StreamingResponse(stream_generator, media_type="text/event-stream")


# 普通get方法
@app.get("/data_get")
async def data_get(index_service: IndexService = Depends(get_index_service)):
    """
    返回GET请求数据
    """
    result = await index_service.data_get()
    return result

# app.include_router(router, prefix="/index", tags=["index模板"])