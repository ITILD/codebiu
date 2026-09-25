"""系统通用动态配置管理端点(管理员): 查看配置组元数据与打码值 / 更新配置组

权限: main:config:read / main:config:update(通用配置为管理员专属, 不进默认用户策略)
"""
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from common.config.dynamic import settings_service
from common.config.server import app
from module_authorization.dependencies.permission import require_permission

router = APIRouter()


class ConfigUpdateRequest(BaseModel):
    """配置组更新请求体: data 为该组字段的(嵌套)dict, 密钥字段缺省保持/空串清除"""

    data: dict = Field(default_factory=dict, description="配置字段键值(嵌套结构)")


@router.get("", summary="获取全部配置组(元数据+打码值)")
async def list_sys_configs(
    current_user_id: str = Depends(require_permission("main", "config", "read")),
) -> dict:
    """
    返回全部动态配置组: 组元数据 + 字段元数据(类型/标题/描述/选项) + 打码后的当前值。
    密钥类字段仅返回 has_value, 不回显明文 —— 该结构直接驱动前端通用配置表单。
    """
    return {"groups": await settings_service.describe_all()}


@router.get("/{group}", summary="获取单个配置组(元数据+打码值)")
async def get_sys_config(
    group: str,
    current_user_id: str = Depends(require_permission("main", "config", "read")),
) -> dict:
    """按组标识返回配置组描述; 未知组名返回 400"""
    return await settings_service.describe(group)


@router.put("/{group}", summary="更新配置组", status_code=status.HTTP_204_NO_CONTENT)
async def update_sys_config(
    group: str,
    body: ConfigUpdateRequest,
    current_user_id: str = Depends(require_permission("main", "config", "update")),
) -> None:
    """
    更新配置组: 校验通过后落库并使缓存失效(请求级配置即时生效)。
    未知组名/字段校验失败返回 400; 密钥字段传空串=清除, 缺省=保持不变。
    """
    await settings_service.update(group, body.data, updated_by=current_user_id)


app.include_router(router, prefix="/sys-configs", tags=["系统配置"])
