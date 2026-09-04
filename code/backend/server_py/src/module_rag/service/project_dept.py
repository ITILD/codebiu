from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_rag.do.project_dept import (
    ProjectDept,
    ProjectDeptCreate,
    ProjectDeptUpdate,
)
from module_rag.do.project_member import RagRole
from module_rag.dao.project_dept import ProjectDeptDao
from module_rag.dao.project import ProjectDao
from module_authorization.dao.dept import DeptDao
import logging

logger = logging.getLogger(__name__)


class ProjectDeptService:
    """项目部门授权服务(部门批量授权,生效档位与个人成员取最高,见 dependencies/permission.py)"""

    def __init__(self, dept_auth_dao: ProjectDeptDao | None = None):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.dao = dept_auth_dao or ProjectDeptDao()
        self._project_dao = ProjectDao()  # 仅用于项目存在性校验
        self._dept_dao = DeptDao()  # 仅用于部门存在性校验

    async def add(self, dept_auth: ProjectDeptCreate) -> str:
        """
        添加部门授权
        :param dept_auth: 部门授权创建数据(role 必须为项目级三档之一)
        :return: 创建的授权记录ID
        """
        # 角色合法性校验
        if dept_auth.role not in RagRole.PROJECT_ROLES:
            raise ValueError(
                f"无效的角色 '{dept_auth.role}'，允许的角色: {'/'.join(RagRole.PROJECT_ROLES)}"
            )
        # 项目存在性校验
        project = await self._project_dao.get(dept_auth.project_id)
        if project is None:
            raise ValueError(f"项目不存在: {dept_auth.project_id}")
        # 部门存在性校验
        dept = await self._dept_dao.get_raw(dept_auth.dept_id)
        if dept is None:
            raise ValueError(f"部门不存在: {dept_auth.dept_id}")
        # 重复授权查重
        existing = await self.dao.get_by_project_and_dept(
            dept_auth.project_id, dept_auth.dept_id
        )
        if existing:
            raise ValueError(f"部门 {dept.name} 已授权，可直接调整档位")
        return await self.dao.add(dept_auth)

    async def delete(self, id: str):
        """
        移除部门授权
        :param id: 授权记录ID
        """
        await self.dao.delete(id)

    async def update(self, id: str, dept_auth: ProjectDeptUpdate):
        """
        更新部门授权档位
        :param id: 授权记录ID
        :param dept_auth: 更新数据(role 必须为项目级三档之一)
        """
        if dept_auth.role is not None and dept_auth.role not in RagRole.PROJECT_ROLES:
            raise ValueError(
                f"无效的角色 '{dept_auth.role}'，允许的角色: {'/'.join(RagRole.PROJECT_ROLES)}"
            )
        await self.dao.update(id, dept_auth)

    async def get(self, id: str) -> ProjectDept | None:
        """
        获取授权详情
        :param id: 授权记录ID
        :return: 授权对象
        """
        return await self.dao.get(id)

    async def list_by_project(
        self, project_id: str, pagination: PaginationParams,
        role: str | None = None,
    ) -> PaginationResponse:
        """
        分页获取项目部门授权列表
        :param project_id: 项目ID
        :param pagination: 分页参数
        :param role: 授权档位精确过滤
        :return: 分页授权列表
        """
        items = await self.dao.list_by_project(project_id, pagination, role=role)
        total = await self.dao.count_by_project(project_id, role=role)
        return PaginationResponse.create(items, total, pagination)
