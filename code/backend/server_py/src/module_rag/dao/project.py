from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update
from common.utils.db.schema.pagination import PaginationParams
from common.config.db import DaoRel
from module_rag.do.project import Project, ProjectCreate, ProjectUpdate


class ProjectDao:
    """项目数据访问对象"""

    @DaoRel
    async def add(
        self, project: ProjectCreate, session: AsyncSession | None = None
    ) -> str:
        """
        新增项目记录
        :param project: 项目创建数据
        :param session: 可选数据库会话
        :return: 新创建项目的ID
        """
        db_project = Project.model_validate(project.model_dump(exclude_unset=True))
        session.add(db_project)
        await session.flush()
        return db_project.id

    @DaoRel
    async def delete(self, id: str, session: AsyncSession | None = None):
        """
        删除项目记录
        :param id: 要删除的项目ID
        :param session: 可选数据库会话
        """
        project = await session.get(Project, id)
        if not project:
            raise ValueError(f"未找到ID为 {id} 的项目")
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
            raise ValueError(f"未找到ID为 {project_id} 的项目")
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
    async def list_all(
        self, pagination: PaginationParams, session: AsyncSession | None = None
    ) -> list[Project]:
        """
        分页查询项目列表
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :return: 项目列表
        """
        statement = select(Project).offset(pagination.offset).limit(pagination.limit)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count(self, session: AsyncSession | None = None) -> int:
        """
        获取项目总数
        :param session: 可选数据库会话
        :return: 项目总数
        """
        statement = select(func.count()).select_from(Project)
        result = await session.exec(statement)
        return result.one()
