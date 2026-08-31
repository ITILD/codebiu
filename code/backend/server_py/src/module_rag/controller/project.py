from fastapi import APIRouter, HTTPException, status, Depends, Query
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_rag.do.project import Project, ProjectCreate, ProjectUpdate, ProjectResponse, KbCategory
from module_rag.service.project import ProjectService
from module_rag.dependencies.project import get_project_service
from module_authorization.dependencies.auth import get_current_user_id
from module_rag.dependencies.permission import require_project_permission
from module_authorization.dependencies.permission import require_permission
from module_rag.config.server import module_app

router = APIRouter()


@router.post(
    "", summary="创建项目", status_code=status.HTTP_201_CREATED, response_model=str
)
async def create_project(
    project: ProjectCreate,
    current_user_id: str = Depends(require_permission("rag", "project", "create")),
    service: ProjectService = Depends(get_project_service),
):
    """
    创建新项目，并自动将当前登录用户设为项目管理员
    :param project: 项目数据(created_by 由系统从 token 自动填充)
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 项目服务依赖注入
    :return: 创建的项目ID
    """
    try:
        return await service.add(project, current_user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/list", summary="分页查询项目列表", response_model=PaginationResponse
)
async def list_projects(
    pagination: PaginationParams = Depends(),
    name: str | None = Query(None, max_length=100, description="项目名称模糊搜索"),
    kb_category: str | None = Query(None, description="知识库分类过滤(personal/project/company)"),
    is_private: bool | None = Query(None, description="私有状态过滤(true=私有/false=公开)"),
    current_user_id: str = Depends(require_permission("rag", "project", "read")),
    service: ProjectService = Depends(get_project_service)
):
    """
    分页查询项目列表(支持多字段过滤)
    :param pagination: 分页参数
    :param name: 项目名称模糊搜索
    :param kb_category: 可选知识库分类过滤(personal/project/company)
    :param is_private: 可选私有状态过滤(true=私有/false=公开)
    :param service: 项目服务依赖注入
    :return: 分页响应结果
    """
    try:
        if kb_category is not None and kb_category not in KbCategory.values():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的知识库分类 '{kb_category}'，允许的值: {'/'.join(KbCategory.values())}",
            )
        return await service.list_all(
            pagination, kb_category=kb_category, name=name, is_private=is_private
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{project_id}", summary="获取单个项目", response_model=Project)
async def get_project(
    project_id: str,
    current_user_id: str = Depends(require_project_permission("project", "read")),
    service: ProjectService = Depends(get_project_service)
):
    """
    获取单个项目详情
    :param project_id: 项目ID
    :param service: 项目服务依赖注入
    :return: 项目详情
    """
    try:
        result = await service.get(project_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="项目未找到"
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete(
    "/{project_id}", summary="删除项目", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_project(
    project_id: str,
    current_user_id: str = Depends(require_project_permission("project", "delete")),
    service: ProjectService = Depends(get_project_service)
):
    """
    删除项目
    :param project_id: 项目ID
    :param service: 项目服务依赖注入
    """
    try:
        await service.delete(project_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put(
    "/{project_id}", summary="更新项目", status_code=status.HTTP_204_NO_CONTENT
)
async def update_project(
    project_id: str,
    project: ProjectUpdate,
    current_user_id: str = Depends(require_project_permission("project", "update")),
    service: ProjectService = Depends(get_project_service)
):
    """
    更新项目
    :param project_id: 项目ID
    :param project: 项目数据
    :param service: 项目服务依赖注入
    """
    try:
        await service.update(project_id, project)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# 注册路由
module_app.include_router(router, prefix="/projects", tags=["项目管理"])
