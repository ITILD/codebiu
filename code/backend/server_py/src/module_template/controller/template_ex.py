import asyncio
import json
from module_template.config.server import module_app
from module_template.dependencies.template import get_template_service
from fastapi import (
    APIRouter,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
    Depends,
    File,
    UploadFile,
)
from fastapi.responses import JSONResponse, StreamingResponse
import logging
from common.config.server import app

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload", summary="上传文件")
async def upload_file(
    file: UploadFile = File(...), service=Depends(get_template_service)
):
    """文件上传接口"""
    try:
        file_content = await file.read()
        file_size = len(file_content)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "filename": file.filename,
                "content_type": file.content_type,
                "size": file_size,
                "message": "File uploaded successfully",
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading file: {str(e)}",
        )


@router.get("/stream", summary="流式返回")
async def stream():
    """流式返回接口"""

    async def event_generator():
        for i in range(10):
            yield f"data: {json.dumps({'event': 'message', 'data': str(i)})}\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# 存储所有连接的客户端：{websocket: name}
active_connections = {}
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    name = websocket.query_params.get("name", "匿名")

    active_connections[websocket] = name
    logger.info(f"用户 {name} 加入聊天室")

    # 广播上线通知
    await broadcast({"sender": "系统", "message": f"{name} 加入了聊天室"})

    try:
        while True:
            # 接收消息
            data = await websocket.receive_text()
            logger.info(f"[{name}] {data}")
            # 广播消息
            await broadcast({"sender": name, "message": data})
    except WebSocketDisconnect:
        logger.info(f"用户 {name} 离开聊天室")
        active_connections.pop(websocket, None)
        await broadcast({"sender": "系统", "message": f"{name} 离开了聊天室"})


async def broadcast(message: dict):
    """广播消息给所有连接的客户端"""
    for connection in list(active_connections.keys()):
        try:
            await connection.send_text(json.dumps(message, ensure_ascii=False))
        except Exception as e:
            # 如果发送失败，移除连接
            active_connections.pop(connection, None)


module_app.include_router(router, prefix="/template_ex", tags=["扩展模板"])
