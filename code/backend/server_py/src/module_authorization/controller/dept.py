from fastapi import APIRouter, HTTPException, status, Depends
from module_authorization.do.dept import DeptCreate, DeptUpdate, DeptResponse, DeptTree
from module_authorization.service.dept import DeptService
from module_authorization.dependencies.dept import get_dept_service
from module_authorization.dependencies.permission import require_permission
from module_authorization.config.server import module_app

router = APIRouter()


@router.post("", summary="创建部门", status_code=status.HTTP_201_CREATED, response_model=DeptResponse,
    dependencies=[Depends(require_permission("sys", "dept", "create"))])
async def create_dept(
    dept: DeptCreate,
    service: DeptService = Depends(get_dept_service),
):
    """创建新部门"""
    try:
        return await service.add(dept)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/tree", summary="获取部门树形结构", response_model=list[DeptTree],
    dependencies=[Depends(require_permission("sys", "dept", "read"))])
async def get_dept_tree(
    service: DeptService = Depends(get_dept_service),
):
    """获取部门树形结构"""
    try:
        return await service.get_tree()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/list", summary="获取部门列表",
    dependencies=[Depends(require_permission("sys", "dept", "read"))])
async def list_depts(
    service: DeptService = Depends(get_dept_service),
):
    """获取所有部门列表(扁平)"""
    try:
        return await service.list_all()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{dept_id}", summary="获取单个部门", response_model=DeptResponse,
    dependencies=[Depends(require_permission("sys", "dept", "read"))])
async def get_dept(
    dept_id: str,
    service: DeptService = Depends(get_dept_service),
):
    """获取单个部门详情"""
    try:
        return await service.get(dept_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{dept_id}", summary="删除部门", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("sys", "dept", "delete"))])
async def delete_dept(
    dept_id: str,
    service: DeptService = Depends(get_dept_service),
):
    """删除部门"""
    try:
        await service.delete(dept_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{dept_id}", summary="更新部门", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("sys", "dept", "update"))])
async def update_dept(
    dept_id: str,
    dept: DeptUpdate,
    service: DeptService = Depends(get_dept_service),
):
    """更新部门"""
    try:
        await service.update(dept_id, dept)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# 注册路由
module_app.include_router(router, prefix="/depts", tags=["部门管理"])
