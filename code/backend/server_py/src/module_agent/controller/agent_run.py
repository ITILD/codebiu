"""智能体运行控制器(结构体配置驱动的一次性运行 + 运行历史查询)"""

from fastapi import APIRouter, Depends

from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_authorization.dependencies.permission import require_permission
from module_agent.dependencies.agent_run import get_agent_run_service
from module_agent.do.agent_run import AgentRunHistory, AgentRunRequest, AgentRunResponse
from module_agent.service.agent_run import AgentRunService

router = APIRouter()


@router.post(
    "/{agent_id}/run",
    summary="运行智能体(结构化输入输出)",
    response_model=AgentRunResponse,
)
async def run_agent(
    agent_id: str,
    request: AgentRunRequest,
    current_user_id: str = Depends(require_permission("agent", "chat", "write")),
    service: AgentRunService = Depends(get_agent_run_service),
) -> AgentRunResponse:
    """按智能体的结构体配置执行一次运行

    - 仅公共或本人创建的智能体可运行(否则 403), 不存在返回 404
    - 输入类型须匹配 agent.input_type; 输出按 output_type 返回字符串或结构化 JSON
    - 成功运行写入运行历史(agent_run 表, 仅本人可见), 返回 run_id 供回看
    """
    return await service.run(agent_id, current_user_id, request)


@router.get(
    "/{agent_id}/runs",
    summary="智能体运行历史(仅本人)",
    response_model=PaginationResponse,
)
async def list_agent_runs(
    agent_id: str,
    pagination: PaginationParams = Depends(),
    current_user_id: str = Depends(require_permission("agent", "chat", "read")),
    service: AgentRunService = Depends(get_agent_run_service),
):
    """分页返回当前用户在指定智能体下的运行记录(输入/输出/模型/时间, 按时间倒序)"""
    return await service.list_runs(agent_id, current_user_id, pagination)


@router.get(
    "/{agent_id}/runs/{run_id}",
    summary="运行详情(含工作流节点轨迹, 仅本人)",
    response_model=AgentRunHistory,
)
async def get_agent_run_detail(
    agent_id: str,
    run_id: str,
    current_user_id: str = Depends(require_permission("agent", "chat", "read")),
    service: AgentRunService = Depends(get_agent_run_service),
):
    """查询单条运行记录详情(工作流智能体的节点级输入/输出/耗时/状态轨迹)"""
    return await service.get_run_detail(agent_id, run_id, current_user_id)


# 注册路由(与 agent 管理共用 /agents 前缀)
from module_agent.config.server import module_app  # noqa: E402

module_app.include_router(router, prefix="/agents", tags=["智能体运行"])
