"""
module_task 任务注册表与 worker 辅助

设计说明(通用任务队列, 预留知识库/文档处理等模块接入):
    1. 新业务模块接入队列时, 在 TASK_TYPES 中注册一个 TaskTypeDef 条目即可:
       - celery_task: 任务在 Celery 中的路由名(与 @celery_app.task(name=...) 一致)
       - default_payload: 前端"新建任务"对话框的默认参数模板
    2. worker 侧通过 update_task_fields() 把 状态/百分比/阶段消息 实时回写 PostgreSQL,
       API 侧读库展示, 并可通过 Celery AsyncResult 读取 broker/backend 侧真实状态做对照。
    3. 后续知识库文档处理只需: 注册新类型 + 实现对应 celery 任务函数, API/前端无需改动。
"""
import asyncio
import threading

from common.config.db import db_manager
from module_task.do.task import TaskTypeDef

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
}


def get_task_type(task_type: str) -> TaskTypeDef | None:
    """按类型编码查询注册表条目"""
    return TASK_TYPES.get(task_type)


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
