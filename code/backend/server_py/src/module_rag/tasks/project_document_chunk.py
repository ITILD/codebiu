"""
知识库全库 chunk 重向量化任务(经 module_task 统一任务队列接入, 系统管理员运维操作)

用途: 系统更换向量模型后, 以指定/当前生效的默认公共向量化模型重算 Milvus 中所有 chunk 向量。

架构约定(与 module_rag.tasks.project_document 一致):
    - controller 通过 TaskQueueService.create() 创建任务, 消息只传 task_queue 表主键
    - 任务函数仅是"异步启动器": 读参数 → 调用功能服务(ProjectDocumentChunkService.revectorize_all) → 双写进度
    - 进度双写: task_queue 表(update_task_fields, 事实来源) + Celery 结果后端(update_state, 对照)
    - worker 内禁止 asyncio.run(asyncpg 连接池与循环绑定), 统一使用 run_async 常驻循环
"""
import logging

from common.config.tasks import app as celery_app
from module_task.do.task import QueueTaskStatus
from module_task.tasks import load_task, run_async, update_task_fields

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="module_rag.tasks.project_document_chunk.revectorize_chunks_task",
    max_retries=1,
)
def revectorize_chunks_task(self, task_id: str):
    """
    全库重向量化 Celery 任务(异步启动器, 仅管理员接口触发)
    :param task_id: task_queue 表主键(payload: model_id, None 时用当前生效的默认公共模型)
    """
    # request 为线程本地对象, 必须在 Celery 工作线程内先捕获 ID
    request_id = self.request.id
    return run_async(_run_revectorize(self, task_id, request_id))


async def _run_revectorize(celery_task, task_id: str, request_id: str | None) -> dict:
    """重向量化任务主体: 读参数 → 以创建者身份复检管理员权限 → 调功能服务(带进度回调) → 双写状态"""
    from module_authorization.config.casbin_rule import is_global_admin
    from common.utils.fastapiEX.exceptions import ForbiddenError
    from module_rag.service.project_document_chunk import ProjectDocumentChunkService

    # 1. 读任务参数与创建者(执行时复检: 仅全局管理员可触发, 权限回收后任务安全失败)
    payload, user_id = await load_task(task_id)
    model_id = payload.get("model_id") or None
    if not is_global_admin(user_id):
        raise ForbiddenError(f"任务创建者 {user_id} 已无全局管理员权限, 重向量化任务终止")

    await update_task_fields(
        task_id, status=QueueTaskStatus.RUNNING,
        progress=0, message="开始全库重向量化", set_started=True,
    )

    # 2. 进度回调: 按文档粒度双写 task_queue 表与 Celery 结果后端
    async def _on_progress(processed_docs: int, total_docs: int,
                           chunks: int, model_label: str, dim_changed: bool):
        progress = round(processed_docs / total_docs * 100, 1) if total_docs else 100.0
        message = (f"重向量化: {processed_docs}/{total_docs} 文档, 已处理 {chunks} 块"
                   f"(维度{'变更' if dim_changed else '一致'})")
        await update_task_fields(task_id, progress=progress, message=message)
        celery_task.update_state(
            task_id=request_id, state="PROGRESS",
            meta={"progress": progress, "message": message,
                  "total": total_docs, "processed": processed_docs,
                  "chunks": chunks, "model": model_label, "dim_changed": dim_changed},
        )

    try:
        # 3. 调用功能服务执行核心逻辑
        result = await ProjectDocumentChunkService().revectorize_all(model_id, _on_progress)

        # 4. 成功收尾(双写)
        await update_task_fields(
            task_id, status=QueueTaskStatus.SUCCESS, progress=100,
            message="重向量化完成", result=result, set_finished=True,
        )
        return result
    except Exception as exc:
        # 失败收尾(错误信息回写, 前端可直接展示)
        logger.error(f"全库重向量化任务失败 task_id={task_id}: {exc}", exc_info=True)
        await update_task_fields(
            task_id, status=QueueTaskStatus.FAILED,
            error=f"{type(exc).__name__}: {exc}", set_finished=True,
        )
        raise
