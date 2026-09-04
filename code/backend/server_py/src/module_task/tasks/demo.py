"""
示例消费任务(模拟文档处理流水线)

演示 Celery worker 的完整生命周期:
    排队(pending) → 开始执行(running) → 阶段性回写进度 → 成功(success)/失败(failed)
进度同时写入两处, 供 API/前端对照检测:
    1. PostgreSQL task_queue 表(状态与百分比的事实来源)
    2. Celery 结果后端(update_state PROGRESS meta, 通过 AsyncResult 读取)
"""
import asyncio
import logging

from common.config.tasks import app as celery_app
from module_task.do.task import QueueTaskStatus
from module_task.tasks import run_async, update_task_fields

logger = logging.getLogger(__name__)

# 流水线阶段定义: (起始百分比, 结束百分比, 阶段名)
_STAGES = [
    (0, 30, "解析文档"),
    (30, 60, "内容分块"),
    (60, 90, "向量化"),
    (90, 100, "写入知识库"),
]


@celery_app.task(name="task.run_demo_document", bind=True)
def run_demo_document(self, task_id: str) -> dict:
    """
    示例文档处理任务(模拟消费进程)
    :param task_id: task_queue 表主键(任务参数从库中读取, 消息只传ID保持轻量)
    :return: 结果 JSON(同时写入 result_backend 与数据库 result 字段)
    """
    # request 为线程本地对象, 必须在 Celery 工作线程内先捕获 ID
    request_id = self.request.id
    # 提交到 worker 专用事件循环(asyncpg 连接池与该循环绑定, 不能跨循环复用)
    return run_async(_run_demo(self, task_id, request_id))


async def _run_demo(celery_task, task_id: str, request_id: str | None) -> dict:
    """异步流水线主体(事件循环内直接回写数据库, 避免频繁建循环)"""
    from common.config.db import db_manager

    from module_task.do.task import TaskQueue

    # 读取任务参数
    async with db_manager.db_rel.session_factory() as session:
        task = await session.get(TaskQueue, task_id)
        if task is None:
            raise ValueError(f"任务 {task_id} 不存在")
        payload: dict = dict(task.payload or {})

    file_name: str = str(payload.get("file_name", "未命名文档"))
    total_pages: int = max(1, int(payload.get("total_pages", 20)))
    duration: float = max(2.0, float(payload.get("duration", 16)))

    await update_task_fields(
        task_id, status=QueueTaskStatus.RUNNING,
        progress=0, message=f"开始处理: {file_name}", set_started=True,
    )

    try:
        # ---- 模拟流水线: 逐阶段推进百分比 ----
        for start, end, stage_name in _STAGES:
            steps = 4  # 每阶段细分 4 次进度回写
            for i in range(1, steps + 1):
                await asyncio.sleep(duration / (len(_STAGES) * steps))

                # 协作式取消检查: API 侧已置 cancelled/revoked 时立即终止
                if await _is_cancelled(task_id):
                    logger.info(f"任务 {task_id} 已被取消, worker 提前退出")
                    return {"cancelled": True}

                progress = start + (end - start) * i / steps
                if stage_name == "解析文档":
                    detail = f"已解析 {int(total_pages * progress / 100)}/{total_pages} 页"
                elif stage_name == "内容分块":
                    detail = f"已生成 {int(progress * 3.2)} 个文本块"
                elif stage_name == "向量化":
                    detail = f"已向量化 {int(progress * 3.2)} 个文本块"
                else:
                    detail = "写入知识库集合 demo_collection"
                message = f"{stage_name}: {detail}"

                # 双写: 数据库(展示事实来源) + Celery 结果后端(状态对照)
                await update_task_fields(
                    task_id, progress=progress, message=message,
                )
                celery_task.update_state(
                    task_id=request_id, state="PROGRESS",
                    meta={"progress": progress, "message": message},
                )

        # ---- 成功收尾 ----
        chunks = int(100 * 3.2)
        result = {
            "file_name": file_name,
            "total_pages": total_pages,
            "chunks": chunks,
            "vectors": chunks,
            "collection": "demo_collection",
        }
        await update_task_fields(
            task_id, status=QueueTaskStatus.SUCCESS, progress=100,
            message="处理完成", result=result, set_finished=True,
        )
        return result

    except Exception as exc:
        # ---- 失败收尾(错误信息回写, 前端可直接展示) ----
        logger.exception(f"任务 {task_id} 执行失败")
        await update_task_fields(
            task_id, status=QueueTaskStatus.FAILED,
            error=f"{type(exc).__name__}: {exc}", set_finished=True,
        )
        raise


async def _is_cancelled(task_id: str) -> bool:
    """协作式取消检查(轻量只读查询)"""
    from common.config.db import db_manager

    from module_task.do.task import TaskQueue

    async with db_manager.db_rel.session_factory() as session:
        task = await session.get(TaskQueue, task_id)
        return bool(
            task and task.status in (QueueTaskStatus.CANCELLED, QueueTaskStatus.REVOKED)
        )
