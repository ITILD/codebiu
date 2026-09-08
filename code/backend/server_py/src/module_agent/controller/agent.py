"""智能体管理控制器(CRUD: 内置公共智能体 + 动态添加自定义简单智能体)"""

from fastapi import APIRouter, Depends, status
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_authorization.dependencies.permission import require_permission
from module_agent.dependencies.agent import get_agent_service
from module_agent.do.agent import Agent, AgentCreate, AgentUpdate
from module_agent.service.agent import AgentService

router = APIRouter()


@router.get("", summary="获取可访问的智能体列表(公共+本人)", response_model=PaginationResponse)
async def list_agents(
    pagination: PaginationParams = Depends(),
    current_user_id: str = Depends(require_permission("agent", "manage", "read")),
    service: AgentService = Depends(get_agent_service),
):
    """分页获取当前用户可访问的智能体(内置公共 + 本人创建)"""
    return await service.list_accessible(current_user_id, pagination)


@router.get("/{agent_id}", summary="获取智能体详情", response_model=Agent)
async def get_agent(
    agent_id: str,
    current_user_id: str = Depends(require_permission("agent", "manage", "read")),
    service: AgentService = Depends(get_agent_service),
):
    """按ID查询智能体详情, 不存在时返回404"""
    result = await service.get(agent_id)
    if not result:
        from common.utils.fastapiEX.exceptions import NotFoundError

        raise NotFoundError("智能体未找到")
    return result


@router.post("", summary="创建自定义简单智能体", status_code=status.HTTP_201_CREATED, response_model=str)
async def create_agent(
    data: AgentCreate,
    current_user_id: str = Depends(require_permission("agent", "manage", "create")),
    service: AgentService = Depends(get_agent_service),
):
    """创建私有简单智能体(名称+描述+系统提示词驱动)"""
    return await service.create(current_user_id, data)


@router.put("/{agent_id}", summary="更新智能体", status_code=status.HTTP_204_NO_CONTENT)
async def update_agent(
    agent_id: str,
    data: AgentUpdate,
    current_user_id: str = Depends(require_permission("agent", "manage", "update")),
    service: AgentService = Depends(get_agent_service),
):
    """更新智能体(仅创建者或管理员)"""
    await service.update(agent_id, current_user_id, data)


@router.delete("/{agent_id}", summary="删除智能体", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    current_user_id: str = Depends(require_permission("agent", "manage", "delete")),
    service: AgentService = Depends(get_agent_service),
):
    """删除智能体(仅创建者或管理员, 内置不可删)"""
    await service.delete(agent_id, current_user_id)


# 注册路由(挂在 /agent/agents 前缀下)
from module_agent.config.server import module_app  # noqa: E402

module_app.include_router(router, prefix="/agents", tags=["智能体管理"])
