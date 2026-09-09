"""
module_task 任务注册表与 worker 辅助

设计说明(通用任务队列, 预留知识库/文档处理等模块接入):
    1. 新业务模块接入队列时, 在 TASK_TYPES 中注册一个 TaskTypeDef 条目即可:
       - celery_task: 任务在 Celery 中的路由名(与 @celery_app.task(name=...) 一致)
       - default_payload: 前端"新建任务"对话框的默认参数模板
    2. worker 侧通过 update_task_fields() 把 状态/百分比/阶段消息 实时回写 PostgreSQL,
       API 侧读库展示, 并可通过 Celery AsyncResult 读取 broker/backend 侧真实状态做对照。
    3. 任务函数统一是"薄启动器": load_task 读参数 → 调用业务模块自己的 service 执行 →
       双写进度。service 保持纯净(不抛 HTTP 异常), 主进程 controller 可直跑同一 service,
       也可经 TaskQueueService.create 入队, 两种执行路径完全兼容(示例任务 demo 除外)。
    4. 任务账户与权限约定(推荐模式):
       - 账户: task_queue.user_id 记录任务创建者, worker 经 load_task 取回作为"任务身份";
       - 权限: 创建时由 controller 鉴权(require_permission / enforce_project_permission),
               执行时 worker 以 user_id 实时查库复检资源权限(casbin/项目档位),
               不快照权限 —— 权限被回收后任务安全失败, 不会越权续跑。
"""
import asyncio
import logging
import threading

from common.config.db import db_manager
from module_task.do.task import TaskTypeDef

logger = logging.getLogger(__name__)

# ################ worker 专用事件循环 ################
# Celery 任务函数是同步的, 每次用 asyncio.run 会创建新事件循环,
# 而 asyncpg 连接与创建它的循环绑定(跨循环复用会崩溃)。
# 因此 worker 进程启动时开一个常驻循环线程, 所有任务协程都提交到该循环执行,
# 使全局连接池(db_manager.db_rel)在进程生命周期内绑定同一个循环。

_worker_loop = asyncio.new_event_loop()
threading.Thread(target=_worker_loop.run_forever, daemon=True, name="task-worker-loop").start()


def run_async(coro):
    """
    在 worker 专用事件循环中执行协程并阻塞等待结果
    (Celery 任务函数内部用; 进程内所有任务共享循环与数据库连接池)
    """
    return asyncio.run_coroutine_threadsafe(coro, _worker_loop).result()

# ################ 任务类型注册表 ################

TASK_TYPES: dict[str, TaskTypeDef] = {
    "demo_document": TaskTypeDef(
        type="demo_document",
        name="示例: 文档处理",
        description="模拟文档处理流水线(解析→分块→向量化→入库), 用于演示任务队列全流程; "
                    "后续知识库模块的真实文档处理任务将替换此实现",
        celery_task="task.run_demo_document",
        default_payload={
            "file_name": "示例文档.pdf",
            "total_pages": 42,
            "duration": 16,
        },
    ),
    "rag_document_parse": TaskTypeDef(
        type="rag_document_parse",
        name="知识库: 文档解析",
        description="解析项目文档: OCR/解析 → 分块策略识别 → 重分块 → 向量化 → 写入向量库;"
                    "以任务创建者绑定的模型执行(未绑定时回退默认公共模型)",
        celery_task="module_rag.tasks.project_document.reparse_document_task",
        default_payload={"document_id": "", "force_preset_id": None},
    ),
    "rag_revectorize": TaskTypeDef(
        type="rag_revectorize",
        name="知识库: 全库重向量化",
        description="系统更换向量模型后, 以指定/当前生效的默认公共向量化模型"
                    "重算 Milvus 中所有文档 chunk 向量(仅系统管理员)",
        celery_task="module_rag.tasks.project_document_chunk.revectorize_chunks_task",
        default_payload={"model_id": None},
    ),
}


def get_task_type(task_type: str) -> TaskTypeDef | None:
    """按类型编码查询注册表条目"""
    return TASK_TYPES.get(task_type)


async def load_task(task_id: str) -> tuple[dict, str]:
    """
    worker 侧读取任务参数与创建者(任务消息只传ID保持轻量, 参数从库中读)
    :param task_id: task_queue 表主键
    :return: (payload参数dict, 创建者user_id)
    :raises ValueError: 任务不存在
    """
    from module_task.do.task import TaskQueue

    async with db_manager.db_rel.session_factory() as session:
        task = await session.get(TaskQueue, task_id)
        if task is None:
            raise ValueError(f"任务 {task_id} 不存在")
        return dict(task.payload or {}), task.user_id


# ################ worker 侧回写辅助 ################

async def update_task_fields(
    task_id: str,
    *,
    status: str | None = None,
    progress: float | None = None,
    message: str | None = None,
    result: dict | None = None,
    error: str | None = None,
    set_started: bool = False,
    set_finished: bool = False,
) -> None:
    """
    worker 侧更新任务字段(独立短事务, 进度可频繁回写)
    :param task_id: 任务ID
    :param status: 目标状态(None 表示不更新)
    :param progress: 完成百分比 0~100
    :param message: 当前阶段描述
    :param result: 执行结果 JSON
    :param error: 失败原因
    :param set_started: 置 started_at 为当前时间(任务开始时)
    :param set_finished: 置 finished_at 为当前时间(任务结束时)
    """
    from datetime import datetime, timezone

    from module_task.do.task import TaskQueue

    async with db_manager.db_rel.session_factory() as session:
        async with session.begin():
            task = await session.get(TaskQueue, task_id)
            if task is None:
                return
            if status is not None:
                task.status = status
            if progress is not None:
                task.progress = max(0.0, min(100.0, float(progress)))
            if message is not None:
                task.message = message
            if result is not None:
                task.result = result
            if error is not None:
                task.error = error
            if set_started and task.started_at is None:
                task.started_at = datetime.now(timezone.utc)
            if set_finished:
                task.finished_at = datetime.now(timezone.utc)


# ################ worker 启动自愈 ################

async def recover_pending_tasks(min_age_seconds: int = 60) -> int:
    """
    兜底重投递: worker 启动时扫描"长期 PENDING 且从未成功投递"的任务
    (celery_task_id 为空, 多为 API 投递瞬间崩溃或 Redis 消息丢失), 重新 send_task。
    消息只携带 task_id, 重复投递安全(消费侧按 ID 读库, 业务执行本身可重入)。
    :param min_age_seconds: 仅处理创建超过该秒数的任务(避开与 API 投递过程竞态)
    :return: 重投递的任务数
    """
    from datetime import datetime, timedelta, timezone

    from sqlmodel import select

    from common.config.tasks import app as celery_app
    from module_task.do.task import QueueTaskStatus, TaskQueue

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=min_age_seconds)
    recovered = 0
    async with db_manager.db_rel.session_factory() as session:
        rows = await session.exec(
            select(TaskQueue).where(
                TaskQueue.status == QueueTaskStatus.PENDING,
                TaskQueue.celery_task_id.is_(None),  # type: ignore[attr-defined]
                TaskQueue.created_at < cutoff,
            )
        )
        stale = list(rows.all())
        for task in stale:
            task_def = get_task_type(task.task_type)
            if task_def is None:
                continue
            try:
                result = celery_app.send_task(
                    task_def.celery_task, args=[task.id],
                    queue="task_queue", priority=task.priority,
                )
                task.celery_task_id = result.id
                await session.commit()
                recovered += 1
                logger.info(f"自愈重投递任务 {task.id}({task.task_type})")
            except Exception as exc:
                logger.warning(f"自愈重投递失败 {task.id}: {exc}")
                await session.rollback()
    if recovered:
        logger.info(f"任务队列自愈完成, 重投递 {recovered} 个遗留任务")
    return recovered


async def init_worker_authorization() -> None:
    """
    worker 进程权限上下文初始化: 轻量构建 casbin enforcer 并从库加载策略。
    仅读不写(默认策略由 API 进程负责同步), 供任务执行时以创建者身份复检权限
    (is_global_admin / enforce_project_permission 均依赖该 enforcer)。
    """
    from module_authorization.config.casbin_rule import auth_manager

    await auth_manager.init_enforcer_only()
