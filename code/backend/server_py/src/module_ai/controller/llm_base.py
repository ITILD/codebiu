from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from module_ai.dependencies.llm_base import LLMBaseService, get_llm_base_service
from module_ai.do.llm_base import (
    ChatRequest,
    EmbeddingRequest,
    CacheClearRequest,
)
from module_ai.config.server import module_app
from module_ai.do.model_config import ModelConfigCreateRequest
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# 控制器层负责处理HTTP请求和响应格式
# 简化的流式响应生成器
async def streaming_generator(responses):
    """简单的流式响应生成器"""
    try:
        async for chunk in responses:
            if chunk.content:
                yield chunk.content
    except Exception as e:
        logger.error(f"流式响应失败: {e}")
        yield "[ERROR]"
    yield "[DONE]"


@router.post("/check_config", summary="配置校验")
async def check_config(
    model_config: ModelConfigCreateRequest,
    llm_service: LLMBaseService = Depends(get_llm_base_service),
):
    """
    校验模型配置是否有效

    - **model_config**: 模型配置对象，包含模型类型、服务类型、URL、API密钥等信息
    """
    try:
        result: bool = await llm_service.check_config(model_config)
        return {"message": "配置校验通过" if result else "配置校验失败:智能程度低"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"配置校验失败: {e}")
        raise HTTPException(status_code=500, detail=f"配置校验失败: {str(e)}")


@router.post("/chat", summary="聊天接口")
async def chat_completion(
    request: ChatRequest, llm_service: LLMBaseService = Depends(get_llm_base_service)
):
    """
    聊天完成接口

    - **model_id**: 模型配置ID或模型标识名称
    - **messages**: 消息内容，可以是字符串或消息列表
    - **streaming**: 是否启用流式响应
    """
    try:
        # 调用LLM服务
        responses = await llm_service.chat_completion(request)
        if request.streaming:
            # 流式响应
            return StreamingResponse(
                content=streaming_generator(responses), media_type="text/event-stream"
            )
        else:
            # 非流式响应
            return responses
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"聊天完成接口失败: {e}")
        raise HTTPException(status_code=500, detail=f"模型调用失败: {str(e)}")


@router.delete("/_test_cache_clear/{model_id}", summary="测试清除模型缓存")
async def _test_cache_clear(
    model_id: str, llm_service: LLMBaseService = Depends(get_llm_base_service)
):
    """
    清除模型缓存

    - **model_id**: 模型配置ID或模型标识名称，为空则清除所有缓存
    """
    try:
        llm_service.clear_cache(model_id)
        if model_id:
            return {"message": f"模型 {model_id} 缓存已清除"}
        else:
            return {"message": "所有模型缓存已清除"}
    except Exception as e:
        logger.error(f"清除缓存失败: {e}")
        raise HTTPException(status_code=500, detail=f"清除缓存失败: {str(e)}")


# 将路由注册到模块应用
module_app.include_router(router, prefix="/llm_base", tags=["模型基础调用"])
