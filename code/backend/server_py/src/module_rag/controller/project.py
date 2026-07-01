from fastapi import APIRouter, HTTPException, status, Depends
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_rag.do.project import Project, ProjectCreate, ProjectUpdate, ProjectResponse
from module_rag.service.project import ProjectService
from module_rag.dependencies.project import get_project_service
from module_rag.config.server import module_app

router = APIRouter()


@router.post(
    "", summary="创建项目", status_code=status.HTTP_201_CREATED, response_model=str
)
async def create_project(
    project: ProjectCreate,
    service: ProjectService = Depends(get_project_service)
):
    """
    创建新项目
    :param project: 项目数据
    :param service: 项目服务依赖注入
    :return: 创建的项目ID
    """
    try:
        return await service.add(project)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/list", summary="分页查询项目列表", response_model=PaginationResponse
)
async def list_projects(
    pagination: PaginationParams = Depends(),
    service: ProjectService = Depends(get_project_service)
):
    """
    分页查询项目列表
    :param pagination: 分页参数
    :param service: 项目服务依赖注入
    :return: 分页响应结果
    """
    try:
        return await service.list_all(pagination)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{project_id}", summary="获取单个项目", response_model=Project)
async def get_project(
    project_id: str,
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# 注册路由
module_app.include_router(router, prefix="/projects", tags=["项目管理"])
