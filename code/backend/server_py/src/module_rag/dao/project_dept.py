from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update
from common.config.db import DaoRel
from common.utils.db.schema.pagination import PaginationParams
from module_rag.do.project_dept import (
    ProjectDept,
    ProjectDeptCreate,
    ProjectDeptUpdate,
)


class ProjectDeptDao:
    """项目部门授权数据访问对象"""

    @DaoRel
    async def add(
        self, dept_auth: ProjectDeptCreate, session: AsyncSession | None = None
    ) -> str:
        """
        新增部门授权记录
        :param dept_auth: 部门授权创建数据
        :param session: 可选数据库会话
        :return: 新创建部门授权的ID
        """
        db_dept_auth = ProjectDept.model_validate(dept_auth.model_dump(exclude_unset=True))
        session.add(db_dept_auth)
        await session.flush()
        return db_dept_auth.id

    @DaoRel
    async def get(
        self, id: str, session: AsyncSession | None = None
    ) -> ProjectDept | None:
        """
        查询单条部门授权
        :param id: 授权记录ID
        :param session: 可选数据库会话
        :return: 授权对象，未找到返回None
        """
        return await session.get(ProjectDept, id)

    @DaoRel
    async def get_by_project_and_dept(
        self, project_id: str, dept_id: str, session: AsyncSession | None = None
    ) -> ProjectDept | None:
        """
        按项目+部门查询授权(用于重复授权查重)
        :param project_id: 项目ID
        :param dept_id: 部门ID
        :param session: 可选数据库会话
        :return: 授权对象，未找到返回None
        """
        statement = select(ProjectDept).where(
            ProjectDept.project_id == project_id,
            ProjectDept.dept_id == dept_id,
        )
        result = await session.exec(statement)
        return result.first()

    @DaoRel
    async def update(
        self,
        id: str,
        dept_auth: ProjectDeptUpdate,
        session: AsyncSession | None = None,
    ):
        """
        更新部门授权档位
        :param id: 授权记录ID
        :param dept_auth: 更新数据
        :param session: 可选数据库会话
        """
        update_data = dept_auth.model_dump(exclude_unset=True)
        stmt = update(ProjectDept).where(ProjectDept.id == id).values(**update_data)
        result = await session.exec(stmt)
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {id} 的部门授权")
        await session.flush()

    @DaoRel
    async def delete(self, id: str, session: AsyncSession | None = None):
        """
        删除部门授权记录
        :param id: 授权记录ID
        :param session: 可选数据库会话
        """
        dept_auth = await session.get(ProjectDept, id)
        if not dept_auth:
            raise ValueError(f"未找到ID为 {id} 的部门授权")
        await session.delete(dept_auth)
        await session.flush()

    @DaoRel
    async def list_by_project(
        self,
        project_id: str,
        pagination: PaginationParams,
        session: AsyncSession | None = None,
        role: str | None = None,
    ) -> list[ProjectDept]:
        """
        分页查询项目的部门授权列表
        :param project_id: 项目ID
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :param role: 授权档位精确过滤
        :return: 部门授权列表
        """
        conditions = [ProjectDept.project_id == project_id]
        if role:
            conditions.append(ProjectDept.role == role)
        statement = (
            select(ProjectDept)
            .where(*conditions)
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count_by_project(
        self,
        project_id: str,
        session: AsyncSession | None = None,
        role: str | None = None,
    ) -> int:
        """
        获取项目部门授权总数(与列表过滤条件保持一致)
        :param project_id: 项目ID
        :param session: 可选数据库会话
        :param role: 授权档位精确过滤
        :return: 授权总数
        """
        conditions = [ProjectDept.project_id == project_id]
        if role:
            conditions.append(ProjectDept.role == role)
        statement = (
            select(func.count())
            .select_from(ProjectDept)
            .where(*conditions)
        )
        result = await session.exec(statement)
        return result.one()

    @DaoRel
    async def delete_by_project(
        self,
        project_id: str,
        session: AsyncSession | None = None,
    ) -> int:
        """
        按项目ID批量删除部门授权(用于删除项目时级联清理)
        :param project_id: 项目ID
        :param session: 可选数据库会话
        :return: 删除的记录数
        """
        statement = select(ProjectDept).where(ProjectDept.project_id == project_id)
        result = await session.exec(statement)
        dept_auths = result.all()
        for item in dept_auths:
            await session.delete(item)
        await session.flush()
        return len(dept_auths)

    @DaoRel
    async def list_roles_by_dept_ids(
        self,
        project_id: str,
        dept_ids: list[str],
        session: AsyncSession | None = None,
    ) -> list[str]:
        """
        鉴权专用: 查询部门链命中的授权档位列表
        :param project_id: 项目ID
        :param dept_ids: 用户部门链(祖级+自身)部门ID集合
        :param session: 可选数据库会话
        :return: 命中的授权档位列表(可能为空)
        """
        if not dept_ids:
            return []
        statement = select(ProjectDept.role).where(
            ProjectDept.project_id == project_id,
            ProjectDept.dept_id.in_(dept_ids),
        )
        result = await session.exec(statement)
        return list(result.all())
