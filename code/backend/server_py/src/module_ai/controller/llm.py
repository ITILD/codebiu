from fastapi import APIRouter, Depends, HTTPException, Request

# from fastapi.responses import StreamingResponse
from module_ai.dependencies.llm import LLMService, get_llm_service
from module_ai.do.llm import (
    ChatRequest,
    EmbeddingRequest,
    CacheClearRequest,
    ModelConfigCheckResponse,
)
from module_ai.config.server import module_app
from module_ai.do.model_config import ModelConfigCreateRequest
from sse_starlette import EventSourceResponse, ServerSentEvent
from module_ai.utils.llm.stream.sse import event_generator

import logging


logger = logging.getLogger(__name__)

router = APIRouter()



@router.post("/check-config", summary="配置校验")
async def check_config(
    model_config: ModelConfigCreateRequest,
    llm_service: LLMService = Depends(get_llm_service),
) -> ModelConfigCheckResponse:
    """
    校验模型配置是否有效

    - **model_config**: 模型配置对象，包含模型类型、服务类型、URL、API密钥等信息
    """
    result: ModelConfigCheckResponse = await llm_service.check_config(model_config)
    return result


@router.post("/check-config-by-model-id", summary="配置校验")
async def check_config_by_model_id(
    model_id: str,
    llm_service: LLMService = Depends(get_llm_service),
):
    """
    校验模型配置是否有效

    - **model_id**: 模型配置ID或模型标识名称
    """
    result: bool = await llm_service.check_config_by_model_id(model_id)
    return {"message": "配置校验通过" if result else "配置校验失败:智能程度低"}


@router.post("/chat", summary="聊天接口 支持流式SSE")
async def chat_completion(
    request: ChatRequest, llm_service: LLMService = Depends(get_llm_service)
):
    """
    聊天完成接口

    - **model_id**: 模型配置ID或模型标识名称
    - **messages**: 消息内容，可以是字符串或消息列表
    - **streaming**: 是否启用流式响应 返回SSE事件流
    """
    try:
        # 调用LLM服务
        responses = await llm_service.chat_completion(request)
        if request.streaming:
            # 流式响应SSE事件流
            return EventSourceResponse(
                event_generator(responses), media_type="text/event-stream"
            )
        else:
            # 非流式响应
            return responses
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"聊天完成接口失败: {e}")
        raise HTTPException(status_code=500, detail=f"模型调用失败: {str(e)}")


@router.delete("/cache/{model_id}", summary="清除模型缓存")
async def _test_cache_clear(
    model_id: str, llm_service: LLMService = Depends(get_llm_service)
):
    """
    按 model_id 前缀匹配清除已缓存的模型实例，使下次请求重新加载模型；model_id 为空时清空全部模型缓存

    - **model_id**: 模型配置ID或模型标识名称，为空则清除所有缓存
    """
    llm_service.clear_cache(model_id)
    if model_id:
        return {"message": f"模型 {model_id} 缓存已清除"}
    else:
        return {"message": "所有模型缓存已清除"}


# 将路由注册到模块应用
module_app.include_router(router, prefix="/llm", tags=["模型基础调用"])
