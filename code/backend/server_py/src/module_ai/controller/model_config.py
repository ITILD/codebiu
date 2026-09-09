from module_ai.config.server import module_app
from module_ai.dependencies.model_config import get_model_config_service
from module_ai.service.model_config import ModelConfigService
from module_ai.do.model_config import (
    ModelConfig,
    ModelConfigCreateRequest,
    ModelConfigCreate,
    ModelConfigUpdate,
    ModelScope,
)
from module_authorization.dependencies.auth import get_current_user
from module_authorization.config.casbin_rule import auth_manager
from module_authorization.dao.user import UserDao
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    InfiniteScrollResponse,
    PaginationParams,
    PaginationResponse,
)

from fastapi import APIRouter, status, Depends, Query
from common.utils.fastapiEX.exceptions import ForbiddenError, NotFoundError
import logging

logger = logging.getLogger(__name__)


router = APIRouter()


def _is_admin(user_id: str) -> bool:
    """判断用户是否为全局管理员(可见全部模型配置)"""
    enforcer = auth_manager.enforcer
    if enforcer is None:
        return False
    return bool(enforcer.has_grouping_policy(user_id, "admin", "*"))


@router.post(
    "",
    summary="创建模型配置",
    status_code=status.HTTP_201_CREATED,
    response_model=str,
)
async def create_model_config(
    model_config: ModelConfigCreateRequest,
    current_user=Depends(get_current_user),
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
    "scope": "user",
    "dept_id": null,
    "is_default": false,
    "display_name": "我的对话模型",
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
    model_config_create = ModelConfigCreate(
        **model_config.model_dump(),
        user_id=current_user.id,  # 直接使用ID
    )
    # 部门模型: 归属当前用户所在部门(必须已有部门)
    if model_config_create.scope == ModelScope.DEPT:
        if not current_user.dept_id:
            raise ValueError("创建部门模型需要先加入部门")
        model_config_create.dept_id = current_user.dept_id
    return await service.add(model_config_create)


@router.get("/list", summary="分页获取模型配置列表", response_model=PaginationResponse)
async def list_model_configs(
    params: PaginationParams = Depends(),
    model: str | None = Query(None, description="模型标识名称模糊搜索"),
    model_type: str | None = Query(None, description="模型类型过滤(chat/embedding/asr/tts等)"),
    server_type: str | None = Query(None, description="服务类型过滤(openai/dashscope/vllm/ollama/aws)"),
    scope: str | None = Query(None, description="归属范围过滤(public/dept/user)"),
    user: str | None = Query(None, description="按所有者用户名模糊过滤(仅管理员生效)"),
    current_user=Depends(get_current_user),
    service: ModelConfigService = Depends(get_model_config_service),
) -> PaginationResponse:
    """
    分页获取模型配置列表(支持多字段过滤; 按当前用户可见性返回公共/部门/本人模型;
    管理员可见全部并可通过 user 参数按所有者用户名过滤)
    """
    is_admin = _is_admin(current_user.id)
    # 仅管理员支持按所有者用户名过滤(先解析为用户ID列表)
    filter_user_ids: list[str] | None = None
    if user and is_admin:
        filter_user_ids = await UserDao().search_ids_by_username(user)
        if not filter_user_ids:
            return PaginationResponse.create([], 0, params)
    result = await service.list_paged(
        params,
        model=model,
        model_type=model_type,
        server_type=server_type,
        scope=scope,
        user_id=current_user.id,
        dept_id=current_user.dept_id,
        is_admin=is_admin,
        filter_user_ids=filter_user_ids,
    )
    # 脱敏: 仅本人私有模型保留明文, 公共/部门/他人私有(含 admin)一律清空 url/api_key
    service.mask_secrets(result.items, current_user.id, is_admin)
    return result


@router.get("/scroll", summary="滚动加载模型配置列表")
async def infinite_scroll_model_configs(
    params: InfiniteScrollParams = Depends(),
    current_user=Depends(get_current_user),
    service: ModelConfigService = Depends(get_model_config_service),
) -> InfiniteScrollResponse:
    """
    无限滚动获取模型配置列表(按当前用户可见性过滤)
    :param params: 滚动参数
    :param service: 模型配置服务依赖注入
    :return: 滚动响应数据
    """
    is_admin = _is_admin(current_user.id)
    result = await service.get_scroll(
        params,
        user_id=current_user.id,
        dept_id=current_user.dept_id,
        is_admin=is_admin,
    )
    # 脱敏: 仅本人私有模型保留明文, 公共/部门/他人私有(含 admin)一律清空 url/api_key
    service.mask_secrets(result.items, current_user.id, is_admin)
    return result


@router.get("/{id}", summary="获取单个模型配置", response_model=ModelConfig)
async def get_model_config(
    id: str,
    current_user=Depends(get_current_user),
    service: ModelConfigService = Depends(get_model_config_service),
) -> ModelConfig:
    """
    获取指定ID的模型配置(url/api_key 仅本人私有模型可见明文, 其余一律脱敏)
    """
    model_config = await service.get(id)
    if not model_config:
        raise NotFoundError(f"未找到ID为 {id} 的模型配置")
    # 脱敏: 仅本人私有模型保留明文, 公共/部门/他人私有(含 admin)一律清空 url/api_key
    service.mask_secrets(model_config, current_user.id, _is_admin(current_user.id))
    return model_config


@router.put("/{id}", summary="更新模型配置", status_code=status.HTTP_204_NO_CONTENT)
async def update_model_config(
    id: str,
    model_config: ModelConfigUpdate,
    current_user=Depends(get_current_user),
    service: ModelConfigService = Depends(get_model_config_service),
):
    """
    更新指定ID的模型配置(仅全局管理员或创建者本人可操作;
    公共模型包括启动 seed 的默认公共模型, 仅管理员可修改)
    """
    existing = await service.get(id)
    if not existing:
        raise NotFoundError(f"未找到ID为 {id} 的模型配置")
    if not (_is_admin(current_user.id) or existing.user_id == current_user.id):
        raise ForbiddenError("无权修改该模型配置(仅创建者本人或全局管理员)")
    await service.update(id, model_config)


@router.delete("/{id}", summary="删除模型配置", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model_config(
    id: str,
    current_user=Depends(get_current_user),
    service: ModelConfigService = Depends(get_model_config_service),
):
    """
    删除指定ID的模型配置(仅全局管理员或创建者本人可操作)
    """
    existing = await service.get(id)
    if not existing:
        raise NotFoundError(f"未找到ID为 {id} 的模型配置")
    if not (_is_admin(current_user.id) or existing.user_id == current_user.id):
        raise ForbiddenError("无权删除该模型配置(仅创建者本人或全局管理员)")
    await service.delete(id)

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
    params = await service.get_default_params(model_name)
    if not params:
        raise NotFoundError(f"未找到模型 {model_name} 的默认参数")
    return {"params": params}


# 将路由注册到模块应用
module_app.include_router(router, prefix="/model-configs", tags=["模型配置"])
