from module_ai.config.server import module_app
from module_ai.dependencies.model_config import get_model_config_service
from module_ai.service.model_config import ModelConfigService
from module_ai.do.model_config import (
    ModelConfig,
    ModelConfigCreateRequest,
    ModelConfigCreate,
    ModelConfigUpdate,
)
from module_authorization.dependencies.auth import get_current_user_id
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    InfiniteScrollResponse,
    PaginationParams,
    PaginationResponse,
)

from fastapi import APIRouter, HTTPException, status, Depends, Query
import logging

logger = logging.getLogger(__name__)


router = APIRouter()


@router.post(
    "",
    summary="创建模型配置",
    status_code=status.HTTP_201_CREATED,
    response_model=str,
)
async def create_model_config(
    model_config: ModelConfigCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: ModelConfigService = Depends(get_model_config_service),
) -> str:
    """
    创建新模型配置
    :param model_config: 模型配置数据
    :param service: 模型配置服务依赖注入
    :return: 创建的模型配置ID
    
    {
    "model_type": "chat",
    "server_type": "ollama",
    "model": "qwen3-vl:235b-cloud",
    "api_key": "1",
    "pay_in": 0,
    "pay_out": 0,
    "input_tokens": 8192,
    "out_tokens": 8192,
    "temperature": 0.7,
    "timeout": 60,
    "no_think": false,
    "extra": {
    }
    }
    """
    try:
        model_config_create = ModelConfigCreate(
            **model_config.model_dump(),
            user_id=current_user_id,  # 直接使用ID
        )
        return await service.add(model_config_create)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/list", summary="分页获取模型配置列表", response_model=PaginationResponse)
async def list_model_configs(
    params: PaginationParams = Depends(),
    model: str | None = Query(None, description="模型标识名称模糊搜索"),
    model_type: str | None = Query(None, description="模型类型过滤(chat/embedding/asr/tts等)"),
    server_type: str | None = Query(None, description="服务类型过滤(openai/dashscope/vllm/ollama/aws)"),
    service: ModelConfigService = Depends(get_model_config_service),
) -> PaginationResponse:
    """
    分页获取模型配置列表(支持多字段过滤)
    :param params: 分页参数
    :param model: 模型标识名称模糊搜索
    :param model_type: 模型类型过滤(chat/embedding/asr/tts等)
    :param server_type: 服务类型过滤(openai/dashscope/vllm/ollama/aws)
    :param service: 模型配置服务依赖注入
    :return: 分页响应数据
    """
    try:
        return await service.list_paged(
            params, model=model, model_type=model_type, server_type=server_type
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/scroll", summary="滚动加载模型配置列表")
async def infinite_scroll_model_configs(
    params: InfiniteScrollParams = Depends(),
    service: ModelConfigService = Depends(get_model_config_service),
) -> InfiniteScrollResponse:
    """
    无限滚动获取模型配置列表
    :param params: 滚动参数
    :param service: 模型配置服务依赖注入
    :return: 滚动响应数据
    """
    try:
        return await service.get_scroll(params)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{id}", summary="获取单个模型配置", response_model=ModelConfig)
async def get_model_config(
    id: str, service: ModelConfigService = Depends(get_model_config_service)
) -> ModelConfig:
    """
    获取指定ID的模型配置
    :param id: 模型配置ID
    :param service: 模型配置服务依赖注入
    :return: 模型配置对象
    """
    try:
        model_config = await service.get(id)
        if not model_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到ID为 {id} 的模型配置",
            )
        return model_config
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put("/{id}", summary="更新模型配置", status_code=status.HTTP_204_NO_CONTENT)
async def update_model_config(
    id: str,
    model_config: ModelConfigUpdate,
    service: ModelConfigService = Depends(get_model_config_service),
):
    """
    更新指定ID的模型配置
    :param id: 模型配置ID
    :param model_config: 更新的模型配置数据
    :param service: 模型配置服务依赖注入
    """
    try:
        await service.update(id, model_config)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete("/{id}", summary="删除模型配置", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model_config(
    id: str, service: ModelConfigService = Depends(get_model_config_service)
):
    """
    删除指定ID的模型配置
    :param id: 模型配置ID
    :param service: 模型配置服务依赖注入
    """
    try:
        await service.delete(id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

# 根据码表选取模型获取默认参数
@router.get("/default-params/{model_name}", summary="获取默认模型参数kv")
async def get_default_model_params(
    model_name: str,
    service: ModelConfigService = Depends(get_model_config_service),
):
    """
    获取指定模型名称的默认参数
    :param model_name: 模型名称
    :param service: 模型配置服务依赖注入
    :return: 模型默认参数
    """
    try:
        params = await service.get_default_params(model_name)
        if not params:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到模型 {model_name} 的默认参数",
            )
        return {"params": params}
    except HTTPException:
        # 保留 404 语义,避免被包装成 500
        raise
    except Exception as e:
        logger.error(f"获取模型 {model_name} 默认参数失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模型 {model_name} 默认参数失败: {str(e)}",
        )


# 将路由注册到模块应用
module_app.include_router(router, prefix="/model-configs", tags=["模型配置"])
