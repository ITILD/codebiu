"""
任务队列服务层

职责:
    - 任务创建: 校验类型注册表 → 落库(pending) → 投递 Celery(记录 celery_task_id)
    - 状态检测: 数据库为主, 同时读取 Celery 结果后端(AsyncResult)做对照/校正
    - 生命周期管理: 取消(revoke)/重试(重新入队)/删除
"""
from datetime import datetime, timezone

from common.config.tasks import app as celery_app
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_task.dao.task import TaskQueueDao
from module_task.do.task import (
    ACTIVE_STATUSES,
    QueueTaskStatus,
    TaskQueue,
    TaskQueueCreate,
    TaskQueueResponse,
    TaskStatsResponse,
    TaskTypeDef,
)
from module_task.tasks import TASK_TYPES, get_task_type

# Celery 队列名(与 app_task.py worker 消费的队列一致)
TASK_QUEUE_NAME = "task_queue"


class TaskNotFoundError(ValueError):
    """任务不存在(控制器应映射为 404, 与其他状态冲突类 400 区分)"""


# Celery 状态 -> 本模块状态(校正用)
_CELERY_STATE_MAP = {
    "SUCCESS": QueueTaskStatus.SUCCESS,
    "FAILURE": QueueTaskStatus.FAILED,
    "REVOKED": QueueTaskStatus.REVOKED,
}


def _to_response(task: TaskQueue) -> TaskQueueResponse:
    """ORM 转 DTO(基础字段映射)"""
    return TaskQueueResponse(
        id=task.id,
        name=task.name,
        task_type=task.task_type,
        payload=task.payload or {},
        priority=task.priority,
        status=task.status,
        progress=task.progress,
        message=task.message,
        result=task.result,
        error=task.error,
        celery_task_id=task.celery_task_id,
        started_at=task.started_at,
        finished_at=task.finished_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _read_celery_state(task: TaskQueue) -> TaskQueueResponse:
    """
    读取 Celery 结果后端的真实状态与百分比, 合并进响应
    (结果后端不可用时静默降级: celery 字段保持 None, 不影响主流程)
    """
    resp = _to_response(task)
    if not task.celery_task_id:
        return resp
    try:
        async_result = celery_app.AsyncResult(task.celery_task_id)
        resp.celery_state = async_result.state
        info = async_result.info
        # PROGRESS 状态下 info 为 worker update_state 写入的 meta
        if async_result.state == "PROGRESS" and isinstance(info, dict):
            resp.celery_progress = info.get("progress")
        elif async_result.state == "SUCCESS" and isinstance(async_result.result, dict):
            resp.result = resp.result or async_result.result
        elif async_result.state == "FAILURE":
            resp.error = resp.error or str(async_result.result)
    except Exception:
        pass
    return resp


class TaskQueueService:
    def __init__(self, dao: TaskQueueDao):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.dao = dao

    # ################ 查询 ################

    async def list_page(
        self,
        pagination: PaginationParams,
        keyword: str | None = None,
        status: str | None = None,
        task_type: str | None = None,
    ) -> PaginationResponse:
        """分页查询任务列表(列表项附带 Celery 状态对照)"""
        items = await self.dao.list_page(
            pagination, keyword=keyword, status=status, task_type=task_type,
        )
        total = await self.dao.count(
            keyword=keyword, status=status, task_type=task_type,
        )
        return PaginationResponse.create(
            [_read_celery_state(t) for t in items], total, pagination,
        )

    async def get(self, task_id: str) -> TaskQueueResponse:
        """
        查询任务详情(含 Celery 侧状态/百分比)
        :raises ValueError: 任务不存在
        """
        task = await self.dao.get(task_id)
        if not task:
            raise ValueError(f"未找到ID为 {task_id} 的任务")
        return _read_celery_state(task)

    async def stats(self) -> TaskStatsResponse:
        """按状态统计任务数(概览卡片/轮询)"""
        raw = await self.dao.stats()
        return TaskStatsResponse(
            total=sum(raw.values()),
            pending=raw.get(QueueTaskStatus.PENDING, 0),
            running=raw.get(QueueTaskStatus.RUNNING, 0),
            success=raw.get(QueueTaskStatus.SUCCESS, 0),
            failed=raw.get(QueueTaskStatus.FAILED, 0),
            cancelled=raw.get(QueueTaskStatus.CANCELLED, 0)
            + raw.get(QueueTaskStatus.REVOKED, 0),
        )

    @staticmethod
    def registry() -> list[TaskTypeDef]:
        """任务类型注册表(供前端渲染下拉与默认模板)"""
        return list(TASK_TYPES.values())

    # ################ 创建/投递 ################

    async def create(self, data: TaskQueueCreate, user_id: str) -> TaskQueueResponse:
        """
        创建任务并投递 Celery 队列
        :param data: 任务数据(类型需在注册表内)
        :param user_id: 创建者用户ID
        :raises ValueError: 类型未注册 / 队列不可用
        """
        task_def = get_task_type(data.task_type)
        if task_def is None:
            registered = ", ".join(TASK_TYPES.keys())
            raise ValueError(
                f"任务类型 {data.task_type} 未注册(可用类型: {registered})"
            )

        task = TaskQueue(
            name=data.name,
            task_type=data.task_type,
            payload=data.payload or {},
            priority=data.priority,
            user_id=user_id,
            status=QueueTaskStatus.PENDING,
        )
        await self.dao.add(task)

        # 投递 Celery(仅传任务ID, 参数由 worker 从库读取, 消息保持轻量)
        try:
            async_result = celery_app.send_task(
                task_def.celery_task,
                args=[task.id],
                queue=TASK_QUEUE_NAME,
            )
            task.celery_task_id = async_result.id
            await self.dao.update(task)
        except Exception as exc:
            # 队列不可用: 标记失败并保留记录, 前端可见失败原因
            task.status = QueueTaskStatus.FAILED
            task.error = f"任务投递失败(队列不可用): {exc}"
            task.finished_at = datetime.now(timezone.utc)
            await self.dao.update(task)
            raise ValueError("任务队列不可用, 请检查 Redis 与 Celery worker") from exc
        return _to_response(task)

    # ################ 状态同步 ################

    async def sync_from_celery(self, task_id: str) -> TaskQueueResponse:
        """
        以 Celery 结果后端为准校正数据库状态(用于 worker 回写中断等异常场景)
        仅在数据库为非终态时校正, 不覆盖已确认的终态。
        """
        task = await self.dao.get(task_id)
        if not task:
            raise ValueError(f"未找到ID为 {task_id} 的任务")

        if task.status in ACTIVE_STATUSES and task.celery_task_id:
            try:
                async_result = celery_app.AsyncResult(task.celery_task_id)
                mapped = _CELERY_STATE_MAP.get(async_result.state)
                if mapped == QueueTaskStatus.SUCCESS:
                    task.status = QueueTaskStatus.SUCCESS
                    task.progress = 100
                    task.message = "处理完成(由结果后端同步)"
                    if isinstance(async_result.result, dict):
                        task.result = async_result.result
                    task.finished_at = datetime.now(timezone.utc)
                    await self.dao.update(task)
                elif mapped in (QueueTaskStatus.FAILED, QueueTaskStatus.REVOKED):
                    task.status = mapped
                    task.error = str(async_result.result) if mapped == QueueTaskStatus.FAILED else "已被撤销(由结果后端同步)"
                    task.finished_at = datetime.now(timezone.utc)
                    await self.dao.update(task)
            except Exception:
                pass  # 结果后端不可用时跳过校正
        return _read_celery_state(task)

    # ################ 生命周期 ################

    async def cancel(self, task_id: str) -> None:
        """
        取消任务(非终态才可取消): Celery revoke + 数据库置 cancelled
        :raises ValueError: 任务不存在或已处于终态
        """
        task = await self.dao.get(task_id)
        if not task:
            raise TaskNotFoundError(f"未找到ID为 {task_id} 的任务")
        if task.status not in ACTIVE_STATUSES:
            raise ValueError(f"任务已结束({task.status}), 无法取消")

        # 先撤销 Celery 侧(排队中直接丢弃; 执行中由 worker 协作式检查提前退出)
        if task.celery_task_id:
            try:
                celery_app.control.revoke(task.celery_task_id, terminate=True)
            except Exception:
                pass  # 撤销失败不阻塞本地取消(worker 仍会检查库中状态)
        task.status = QueueTaskStatus.CANCELLED
        task.message = "任务已取消"
        task.finished_at = datetime.now(timezone.utc)
        await self.dao.update(task)

    async def retry(self, task_id: str) -> TaskQueueResponse:
        """
        重试任务(仅终态任务): 重置状态后重新投递
        :raises ValueError: 任务不存在/未结束/类型未注册
        """
        task = await self.dao.get(task_id)
        if not task:
            raise TaskNotFoundError(f"未找到ID为 {task_id} 的任务")
        if task.status in ACTIVE_STATUSES:
            raise ValueError("任务仍在进行中, 无需重试")

        task_def = get_task_type(task.task_type)
        if task_def is None:
            raise ValueError(f"任务类型 {task.task_type} 已从注册表移除, 无法重试")

        task.status = QueueTaskStatus.PENDING
        task.progress = 0
        task.message = None
        task.result = None
        task.error = None
        task.finished_at = None
        try:
            async_result = celery_app.send_task(
                task_def.celery_task, args=[task.id], queue=TASK_QUEUE_NAME,
            )
            task.celery_task_id = async_result.id
        except Exception as exc:
            task.status = QueueTaskStatus.FAILED
            task.error = f"任务投递失败(队列不可用): {exc}"
            task.finished_at = datetime.now(timezone.utc)
            await self.dao.update(task)
            raise ValueError("任务队列不可用, 请检查 Redis 与 Celery worker") from exc
        await self.dao.update(task)
        return _to_response(task)

    async def delete(self, task_id: str) -> None:
        """删除任务记录(任何状态均可删除)"""
        await self.dao.delete(task_id)
