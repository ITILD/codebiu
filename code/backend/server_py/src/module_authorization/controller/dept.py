from fastapi import APIRouter, status, Depends
from common.utils.fastapiEX.exceptions import NotFoundError
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
    # 父部门不存在/部门重名校验失败抛 ValueError, 由全局处理器映射为 400
    return await service.add(dept)


@router.get("/tree", summary="获取部门树形结构", response_model=list[DeptTree],
    dependencies=[Depends(require_permission("sys", "dept", "read"))])
async def get_dept_tree(
    service: DeptService = Depends(get_dept_service),
):
    """全量加载部门并按 parent_id 组装为树形结构(各层级按 order_num 升序)
    父部门缺失的孤儿节点会提升为根节点,避免数据丢失
    """
    return await service.get_tree()


@router.get("/list", summary="获取部门列表",
    dependencies=[Depends(require_permission("sys", "dept", "read"))])
async def list_depts(
    service: DeptService = Depends(get_dept_service),
):
    """获取所有部门列表(扁平)"""
    return await service.list_all()


@router.get("/{dept_id}", summary="获取单个部门", response_model=DeptResponse,
    dependencies=[Depends(require_permission("sys", "dept", "read"))])
async def get_dept(
    dept_id: str,
    service: DeptService = Depends(get_dept_service),
):
    """获取单个部门详情, 部门不存在时返回404"""
    try:
        return await service.get(dept_id)
    except ValueError as e:
        # dao/service 层 not-found 抛 ValueError, 此处转为 404
        raise NotFoundError(str(e))


@router.delete("/{dept_id}", summary="删除部门", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("sys", "dept", "delete"))])
async def delete_dept(
    dept_id: str,
    service: DeptService = Depends(get_dept_service),
):
    """删除指定部门:存在子部门时禁止删除(返回400),部门不存在同样报错(400)
    不做子树级联删除,成功返回204
    """
    # 存在子部门等校验失败抛 ValueError, 由全局处理器映射为 400
    await service.delete(dept_id)


@router.put("/{dept_id}", summary="更新部门", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("sys", "dept", "update"))])
async def update_dept(
    dept_id: str,
    dept: DeptUpdate,
    service: DeptService = Depends(get_dept_service),
):
    """按ID部分更新部门字段(仅传传入的字段),调整 parent_id 时自动重算 ancestors 祖先链
    部门不存在或参数非法返回400,成功返回204
    """
    # 参数校验失败抛 ValueError, 由全局处理器映射为 400
    await service.update(dept_id, dept)


# 注册路由
module_app.include_router(router, prefix="/depts", tags=["部门管理"])
