from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_rag.do.project import Project, ProjectCreate, ProjectUpdate, ProjectResponse
from module_rag.dao.project import ProjectDao


class ProjectService:
    """项目服务"""

    def __init__(self, project_dao: ProjectDao):
        self.project_dao = project_dao or ProjectDao()

    async def add(self, project: ProjectCreate) -> str:
        """
        创建项目
        :param project: 项目创建数据
        :return: 创建的项目ID
        """
        return await self.project_dao.add(project)

    async def delete(self, project_id: str):
        """
        删除项目
        :param project_id: 项目ID
        """
        await self.project_dao.delete(project_id)

    async def update(self, project_id: str, project: ProjectUpdate):
        """
        更新项目
        :param project_id: 项目ID
        :param project: 项目更新数据
        """
        await self.project_dao.update(project_id, project)

    async def get(self, project_id: str) -> Project | None:
        """
        获取项目详情
        :param project_id: 项目ID
        :return: 项目对象
        """
        return await self.project_dao.get(project_id)

    async def list_all(self, pagination: PaginationParams) -> PaginationResponse:
        """
        分页获取项目列表
        :param pagination: 分页参数
        :return: 分页项目列表
        """
        items = await self.project_dao.list_all(pagination)
        total = await self.project_dao.count()
        return PaginationResponse.create(items, total, pagination)
