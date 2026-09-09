from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update, or_, exists
from sqlalchemy import false
from common.utils.db.schema.pagination import PaginationParams
from common.config.db import DaoRel
from common.utils.fastapiEX.exceptions import NotFoundError
from module_rag.do.project import Project, ProjectCreate, ProjectUpdate
from module_rag.do.project_member import ProjectMember
from module_rag.do.project_dept import ProjectDept


class ProjectDao:
    """项目数据访问对象"""

    @DaoRel
    async def add(
        self, project: Project, session: AsyncSession | None = None
    ) -> str:
        """
        新增项目记录
        :param project: 项目数据库对象(包含 created_by)
        :param session: 可选数据库会话
        :return: 新创建项目的ID
        """
        session.add(project)
        await session.flush()
        return project.id

    @DaoRel
    async def delete(self, id: str, session: AsyncSession | None = None):
        """
        删除项目记录
        :param id: 要删除的项目ID
        :param session: 可选数据库会话
        """
        project = await session.get(Project, id)
        if not project:
            raise NotFoundError(f"未找到ID为 {id} 的项目")
        await session.delete(project)
        await session.flush()

    @DaoRel
    async def update(
        self,
        project_id: str,
        project: ProjectUpdate,
        session: AsyncSession | None = None,
    ):
        """
        更新项目记录
        :param project_id: 要更新的项目ID
        :param project: 项目更新数据
        :param session: 可选数据库会话
        """
        update_data = project.model_dump(exclude_unset=True)
        stmt = update(Project).where(Project.id == project_id).values(**update_data)
        result = await session.exec(stmt)
        if result.rowcount == 0:
            raise NotFoundError(f"未找到ID为 {project_id} 的项目")
        await session.flush()

    @DaoRel
    async def get(self, id: str, session: AsyncSession | None = None) -> Project | None:
        """
        查询单个项目
        :param id: 要查询的项目ID
        :param session: 可选数据库会话
        :return: 项目对象，未找到返回None
        """
        return await session.get(Project, id)

    @DaoRel
    async def list_paged(
        self, pagination: PaginationParams, session: AsyncSession | None = None,
        name: str | None = None,
        kb_category: str | None = None,
        is_private: bool | None = None,
        viewer_id: str | None = None,
        dept_chain: list[str] | None = None,
    ) -> list[Project]:
        """
        分页查询项目列表(支持多字段过滤 + 查看者可见性)
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :param name: 项目名称模糊匹配
        :param kb_category: 可选知识库分类过滤(personal/project/company)
        :param is_private: 可选私有状态过滤(true=私有/false=公开)
        :param viewer_id: 查看者用户ID(传入时私有库仅 创建者/直连成员/部门授权 可见; None 不过滤,管理员审计用)
        :param dept_chain: 查看者部门链(与 viewer_id 配套,一次查询复用)
        :return: 项目列表
        """
        conditions = []
        if name:
            conditions.append(Project.name.contains(name))
        if kb_category is not None:
            conditions.append(Project.kb_category == kb_category)
        if is_private is not None:
            conditions.append(Project.is_private == is_private)
        if viewer_id:
            conditions.append(
                self._visibility_condition(viewer_id, dept_chain or [])
            )

        statement = select(Project)
        if conditions:
            statement = statement.where(*conditions)
        statement = statement.offset(pagination.offset).limit(pagination.limit)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count(
        self, session: AsyncSession | None = None,
        name: str | None = None,
        kb_category: str | None = None,
        is_private: bool | None = None,
        viewer_id: str | None = None,
        dept_chain: list[str] | None = None,
    ) -> int:
        """
        获取项目总数(与列表过滤条件保持一致)
        :param session: 可选数据库会话
        :param name: 项目名称模糊匹配
        :param kb_category: 可选知识库分类过滤(personal/project/company)
        :param is_private: 可选私有状态过滤(true=私有/false=公开)
        :param viewer_id: 查看者用户ID(可见性过滤,同 list_paged)
        :param dept_chain: 查看者部门链(与 viewer_id 配套)
        :return: 项目总数
        """
        conditions = []
        if name:
            conditions.append(Project.name.contains(name))
        if kb_category is not None:
            conditions.append(Project.kb_category == kb_category)
        if is_private is not None:
            conditions.append(Project.is_private == is_private)
        if viewer_id:
            conditions.append(
                self._visibility_condition(viewer_id, dept_chain or [])
            )

        statement = select(func.count()).select_from(Project)
        if conditions:
            statement = statement.where(*conditions)
        result = await session.exec(statement)
        return result.one()

    @staticmethod
    def _visibility_condition(viewer_id: str, dept_chain: list[str]):
        """构建查看者可见性条件: 公开库全员可见, 私有库仅 创建者/直连成员/部门授权 可见(v4 5.1)"""
        member_exists = exists(
            select(1).where(
                ProjectMember.project_id == Project.id,
                ProjectMember.user_id == viewer_id,
            )
        )
        # 用户无部门时用 false() 占位, 禁止生成 in_([]) 非法 SQL(v4 5.1 注 2)
        dept_exists = (
            exists(
                select(1).where(
                    ProjectDept.project_id == Project.id,
                    ProjectDept.dept_id.in_(dept_chain),
                )
            )
            if dept_chain
            else false()
        )
        return or_(
            Project.is_private == False,  # noqa: E712 公开库
            Project.created_by == viewer_id,  # 自己创建的
            member_exists,
            dept_exists,
        )
