# src/module_rag/tasks/document_tasks.py
import asyncio
import logging

from celery import shared_task

# 导入 Service 和它需要的依赖
from module_rag.service.project_document import ProjectDocumentService
from module_rag.dao.project_document import ProjectDocumentDao
from module_rag.dao.project import ProjectDao
from module_rag.service.user_model import UserModelService
from module_ai.service.llm_base import LLMBaseService
from module_ai.service.model_config import ModelConfigService
from common.config.tasks import app as celery_app

logger = logging.getLogger(__name__)

# @shared_task(bind=True, name="module_rag.tasks.project_document.reparse_document_task", max_retries=3)
@celery_app.task(
    bind=True,
    name="module_rag.tasks.project_document.reparse_document_task",
    max_retries=3
)
def reparse_document_task(self, document_id: str, user_id: str, force_preset_id: str | None = None):
    """
    Celery 异步任务：仅仅作为异步启动器，调用现有的 Service 逻辑
    """
    try:
        logger.info(f"Celery 开始执行异步解析任务: {document_id}")
        
        # 定义一个内部的 async 函数，用于实例化依赖并调用 Service
        async def _execute_service():
            # 1. 在 Worker 进程中手动实例化依赖 (替代 FastAPI 的 Depends)
            doc_dao = ProjectDocumentDao()
            proj_dao = ProjectDao()
            user_service = UserModelService()
            llm_service = LLMBaseService()
            model_service = ModelConfigService()
            
            # 2. 实例化你的 Service
            service = ProjectDocumentService(
                document_dao=doc_dao,
                project_dao=proj_dao,
                user_model_service=user_service,
                llm_base_service=llm_service,
                model_config_service=model_service
            )
            
            # 3. 调用你写在 Service 里的核心逻辑！(代码零重复)
            return await service.reparse_document(document_id, user_id, force_preset_id)

        # 在同步的 Celery Worker 中安全地运行异步代码
        return asyncio.run(_execute_service())

    except Exception as e:
        logger.error(f"Celery 异步解析失败 document_id={document_id}: {e}", exc_info=True)
        # 触发 Celery 的重试机制 (例如 60 秒后重试)
        raise self.retry(exc=e, countdown=60)