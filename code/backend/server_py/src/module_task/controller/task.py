from fastapi import APIRouter, Depends, Query, status

from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_authorization.dependencies.permission import require_permission
from module_task.config.server import module_app
from module_task.dependencies.task import get_task_queue_service
from module_task.do.task import TaskQueueCreate, TaskQueueResponse, TaskStatsResponse
from module_task.service.task import TaskQueueService

router = APIRouter()


@router.post("", summary="创建任务并投递队列", status_code=status.HTTP_201_CREATED, response_model=str)
async def create_task(
    data: TaskQueueCreate,
    current_user_id: str = Depends(require_permission("task", "queue", "create")),
    service: TaskQueueService = Depends(get_task_queue_service),
) -> str:
    """
    创建任务(参数 JSON 落库, 投递 Celery 队列由 worker 消费)
    :param data: 任务数据(名称/类型/参数)
    :param current_user_id: 当前用户ID(权限依赖注入)
    :return: 任务ID
    """
    task = await service.create(data, current_user_id)
    return task.id


@router.get("/registry", summary="查询任务类型注册表", response_model=list)
async def get_registry(
    current_user_id: str = Depends(require_permission("task", "queue", "read")),
    service: TaskQueueService = Depends(get_task_queue_service),
) -> list:
    """
    查询已注册的任务类型(前端类型下拉/默认参数模板)
    """
    return [t.model_dump() for t in service.registry()]


@router.get("/stats", summary="按状态统计任务数", response_model=TaskStatsResponse)
async def get_stats(
    current_user_id: str = Depends(require_permission("task", "queue", "read")),
    service: TaskQueueService = Depends(get_task_queue_service),
) -> TaskStatsResponse:
    """任务状态统计(概览卡片, 供轮询刷新)"""
    return await service.stats()


@router.get("/list", summary="分页查询任务列表", response_model=PaginationResponse)
async def list_tasks(
    pagination: PaginationParams = Depends(),
    keyword: str | None = Query(None, max_length=200, description="任务名称模糊搜索"),
    task_status: str | None = Query(None, alias="status", description="状态过滤(pending/running/success/failed/cancelled)"),
    task_type: str | None = Query(None, description="任务类型过滤"),
    current_user_id: str = Depends(require_permission("task", "queue", "read")),
    service: TaskQueueService = Depends(get_task_queue_service),
) -> PaginationResponse:
    """
    分页查询任务列表(列表项含 Celery 状态对照字段)
    """
    return await service.list_page(
        pagination, keyword=keyword, status=task_status, task_type=task_type,
    )


@router.get("/{task_id}", summary="查询任务详情", response_model=TaskQueueResponse)
async def get_task(
    task_id: str,
    current_user_id: str = Depends(require_permission("task", "queue", "read")),
    service: TaskQueueService = Depends(get_task_queue_service),
) -> TaskQueueResponse:
    """任务详情(含 Celery 侧状态/百分比对照)"""
    # 任务不存在 → 404(service 层 NotFoundError 直接映射)
    return await service.get(task_id)


@router.post("/{task_id}/sync", summary="从Celery同步任务状态", response_model=TaskQueueResponse)
async def sync_task(
    task_id: str,
    current_user_id: str = Depends(require_permission("task", "queue", "update")),
    service: TaskQueueService = Depends(get_task_queue_service),
) -> TaskQueueResponse:
    """
    以 Celery 结果后端为准校正数据库状态(worker 回写中断时使用)
    """
    return await service.sync_from_celery(task_id)


@router.post("/{task_id}/cancel", summary="取消任务", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_task(
    task_id: str,
    current_user_id: str = Depends(require_permission("task", "queue", "update")),
    service: TaskQueueService = Depends(get_task_queue_service),
) -> None:
    """
    取消排队/执行中的任务(Celery revoke + 数据库置 cancelled)
    """
    # 任务不存在 → 404(service 层 TaskNotFoundError), 状态冲突 → 400(service 层 BusinessError)
    await service.cancel(task_id)


@router.post("/{task_id}/retry", summary="重试任务", response_model=TaskQueueResponse)
async def retry_task(
    task_id: str,
    current_user_id: str = Depends(require_permission("task", "queue", "update")),
    service: TaskQueueService = Depends(get_task_queue_service),
) -> TaskQueueResponse:
    """
    重试已结束的任务(重置进度后重新投递队列)
    """
    # 任务不存在 → 404(service 层 TaskNotFoundError), 状态冲突 → 400(service 层 BusinessError)
    return await service.retry(task_id)


@router.delete("/{task_id}", summary="删除任务", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: str,
    current_user_id: str = Depends(require_permission("task", "queue", "delete")),
    service: TaskQueueService = Depends(get_task_queue_service),
) -> None:
    """删除任务记录(任何状态均可删除)"""
    # 任务不存在 → 404(dao 层 NotFoundError 直接映射)
    await service.delete(task_id)


module_app.include_router(router, prefix="/tasks", tags=["任务队列"])
