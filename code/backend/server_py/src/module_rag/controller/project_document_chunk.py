from fastapi import (
    APIRouter,
    HTTPException,
    status,
    Depends,
    UploadFile,
    File,
    Form,
)
from pydantic import BaseModel, Field
from common.utils.fastapiEX.exceptions import NotFoundError
from module_rag.config.server import module_app
from module_rag.do.project_document_chunk import SearchRequest,ProjectDocumentChunkSearchResponse
from module_authorization.dependencies.auth import get_current_user_id, get_current_user
from module_authorization.config.casbin_rule import auth_manager
from module_rag.dependencies.project_document_chunk import get_project_document_chunk_service
from module_rag.service.project_document_chunk import ProjectDocumentChunkService
from module_task.do.task import TaskQueueCreate
from module_task.service.task import TaskQueueService
from module_task.dependencies.task import get_task_queue_service

router = APIRouter()

# task_queue 库中状态 -> Celery 状态(status 接口响应格式兼容, 结果后端不可用时兜底)
_DB_STATE_TO_CELERY = {
    "pending": "PENDING",
    "running": "PROGRESS",
    "success": "SUCCESS",
    "failed": "FAILURE",
    "cancelled": "REVOKED",
    "revoked": "REVOKED",
}


def _is_admin(user_id: str) -> bool:
    """判断用户是否为全局管理员(与 module_ai.controller.model_config 同规则)"""
    enforcer = auth_manager.enforcer
    if enforcer is None:
        return False
    return bool(enforcer.has_grouping_policy(user_id, "admin", "*"))


class RevectorizeRequest(BaseModel):
    """重向量化请求体"""

    model_id: str | None = Field(
        None, description="目标向量化模型配置ID(留空使用当前生效的默认公共向量化模型)"
    )


@router.post(
    "/search-by-question",
    response_model=list[ProjectDocumentChunkSearchResponse],  # 如果有定义，请取消注释
    summary="检索项目相似文档块",
)
async def chunks_by_question(
    request: SearchRequest,
    # 【关键】自动从 Token 中解析当前登录用户的 ID，无需前端手动传
    user_id: str = Depends(get_current_user_id),
    project_document_chunk_service: ProjectDocumentChunkService = Depends(get_project_document_chunk_service),
) -> list[ProjectDocumentChunkSearchResponse]:
    """
    根据文本内容在指定项目中检索最相关的文档块 (逻辑内联版)
    """
    return await project_document_chunk_service.search(request, user_id)


# ############################# 全库重向量化(系统管理员) #############################

@router.post(
    "/revectorize",
    summary="全库重向量化(系统管理员): 以指定/默认公共向量化模型重算所有 chunk 向量",
    status_code=status.HTTP_202_ACCEPTED,
)
async def revectorize_chunks(
    request: RevectorizeRequest,
    current_user=Depends(get_current_user),
    task_service: TaskQueueService = Depends(get_task_queue_service),
):
    """
    经统一任务队列提交全库 chunk 重向量化任务(系统管理员专用)
    :param request: 目标模型配置ID(留空使用当前生效的默认公共向量化模型)
    :param task_service: 统一任务队列服务依赖注入
    :return: {"task_id": task_queue任务ID}(用 GET /revectorize/status/{task_id} 查询进度, 亦可在任务队列页跟踪)
    """
    if not _is_admin(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅系统管理员可执行全库重向量化")
    task = await task_service.create(
        TaskQueueCreate(
            name="全库重向量化",
            task_type="rag_revectorize",
            payload={"model_id": request.model_id},
        ),
        current_user.id,
    )
    return {"task_id": task.id, "message": "重向量化任务已提交"}


@router.get(
    "/revectorize/status/{task_id}",
    summary="查询全库重向量化任务进度(系统管理员)",
)
async def revectorize_status(
    task_id: str,
    current_user=Depends(get_current_user),
    task_service: TaskQueueService = Depends(get_task_queue_service),
):
    """
    查询重向量化任务状态与进度(系统管理员专用; 以 task_queue 表为主, Celery 结果后端对照)
    :param task_id: POST /revectorize 返回的 task_queue 任务ID
    :return: {"task_id", "state", "meta"/"error"}(PROGRESS 时 meta 含 total/processed/chunks/model)
    """
    if not _is_admin(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅系统管理员可查询重向量化进度")
    try:
        resp = await task_service.get(task_id)
    except ValueError as e:
        # 任务不存在 -> 404(NotFoundError), 与参数错误的400区分
        raise NotFoundError(str(e))

    # Celery 侧状态优先(实时), 库中状态兜底(结果后端不可用时)
    state = resp.celery_state or _DB_STATE_TO_CELERY.get(resp.status, "PENDING")
    response: dict = {"task_id": task_id, "state": state}
    if state == "PROGRESS":
        # 完整 meta 来自 worker update_state; 兜底用库中进度
        response["meta"] = resp.celery_meta or {
            "progress": resp.celery_progress if resp.celery_progress is not None else resp.progress,
            "message": resp.message,
        }
    elif state == "FAILURE":
        response["error"] = resp.error or "任务执行失败"
    return response


# 注册路由
module_app.include_router(router, prefix="/project-document-chunks", tags=["项目文档块量管理"])
