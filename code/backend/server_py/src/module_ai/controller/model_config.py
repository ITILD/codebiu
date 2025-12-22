from module_ai.config.server import module_app
from module_ai.dependencies.model_config import get_model_config_service
from module_ai.service.model_config import ModelConfigService
from module_ai.do.model_config import (
    ModelConfig,
    ModelConfigCreateRequest,
    ModelConfigCreate,
    ModelConfigUpdate,
)
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    InfiniteScrollResponse,
    PaginationParams,
    PaginationResponse,
)

from fastapi import APIRouter, HTTPException, status, Depends
import logging

logger = logging.getLogger(__name__)


router = APIRouter()


def get_current_user_id() -> str:
    """
    mock获取当前用户ID
    :return: 当前用户ID
    mock 数据: admin
    """
    return "admin"  # 示例用户ID，实际应从认证系统获取


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
    service: ModelConfigService = Depends(get_model_config_service),
) -> PaginationResponse:
    """
    分页获取模型配置列表
    :param params: 分页参数
    :param service: 模型配置服务依赖注入
    :return: 分页响应数据
    """
    try:
        return await service.list_all(params)
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
@router.get("/default_params/{model_name}", summary="获取默认模型参数kv")
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
    except Exception as e:
        logger.error(f"获取模型 {model_name} 默认参数失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模型 {model_name} 默认参数失败: {str(e)}",
        )


# 将路由注册到模块应用
module_app.include_router(router, prefix="/model_config", tags=["模型配置"])
