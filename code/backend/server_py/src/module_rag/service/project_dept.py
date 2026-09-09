from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from common.utils.fastapiEX.exceptions import ConflictError, NotFoundError
from module_rag.do.project_dept import (
    ProjectDept,
    ProjectDeptCreate,
    ProjectDeptUpdate,
)
from module_rag.do.project_member import RagRole
from module_rag.dao.project_dept import ProjectDeptDao
from module_rag.dao.project_member import ProjectMemberDao
from module_rag.dao.project import ProjectDao
from module_authorization.dao.dept import DeptDao
import logging

logger = logging.getLogger(__name__)


class ProjectDeptService:
    """项目部门授权服务(部门批量授权,生效档位与个人成员取最高,见 dependencies/permission.py)"""

    def __init__(
        self,
        dept_auth_dao: ProjectDeptDao | None = None,
        member_dao: ProjectMemberDao | None = None,
    ):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.dao = dept_auth_dao or ProjectDeptDao()
        self._project_dao = ProjectDao()  # 仅用于项目存在性校验
        self._dept_dao = DeptDao()  # 仅用于部门存在性校验
        # 直连成员计数(保底校验时直连成员来源的 admin 也计入)
        self._member_dao = member_dao or ProjectMemberDao()

    async def _assert_admin_remaining(
        self,
        project_id: str,
        exclude_dept_auth_id: str | None = None,
    ) -> None:
        """移除/降级后必须仍有激活的 project_admin(直连成员或部门授权来源均计入, v4 3.2)"""
        direct = await self._member_dao.count_admins(project_id)
        via_dept = await self.dao.count_admins(project_id, exclude_id=exclude_dept_auth_id)
        if direct + via_dept == 0:
            raise ConflictError("必须至少保留一个项目管理员(project_admin)")

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
            raise NotFoundError(f"项目不存在: {dept_auth.project_id}")
        # 部门存在性校验
        dept = await self._dept_dao.get_raw(dept_auth.dept_id)
        if dept is None:
            raise NotFoundError(f"部门不存在: {dept_auth.dept_id}")
        # 重复授权查重
        existing = await self.dao.get_by_project_and_dept(
            dept_auth.project_id, dept_auth.dept_id
        )
        if existing:
            raise ConflictError(f"部门 {dept.name} 已授权，可直接调整档位")
        return await self.dao.add(dept_auth)

    async def delete(self, id: str):
        """
        移除部门授权(目标是 project_admin 档位时校验保底, 否则 409)
        :param id: 授权记录ID
        """
        dept_auth = await self.dao.get(id)
        if dept_auth is None:
            raise NotFoundError(f"未找到ID为 {id} 的部门授权")
        if dept_auth.role == RagRole.PROJECT_ADMIN:
            await self._assert_admin_remaining(
                dept_auth.project_id, exclude_dept_auth_id=id
            )
        await self.dao.delete(id)

    async def update(self, id: str, dept_auth: ProjectDeptUpdate):
        """
        更新部门授权档位(将 project_admin 档位降级时校验保底, 否则 409)
        :param id: 授权记录ID
        :param dept_auth: 更新数据(role 必须为项目级三档之一)
        """
        if dept_auth.role is not None and dept_auth.role not in RagRole.PROJECT_ROLES:
            raise ValueError(
                f"无效的角色 '{dept_auth.role}'，允许的角色: {'/'.join(RagRole.PROJECT_ROLES)}"
            )
        if dept_auth.role is not None and dept_auth.role != RagRole.PROJECT_ADMIN:
            existing = await self.dao.get(id)
            if existing is None:
                raise NotFoundError(f"未找到ID为 {id} 的部门授权")
            if existing.role == RagRole.PROJECT_ADMIN:
                await self._assert_admin_remaining(
                    existing.project_id, exclude_dept_auth_id=id
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
