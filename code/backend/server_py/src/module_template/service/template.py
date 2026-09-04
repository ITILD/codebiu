# self
from common.utils.db.schema.pagination import InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse
from module_template.do.template import Template, TemplateCreate, TemplateUpdate, TemplateBatchDelete
from module_template.dao.template import TemplateDao

# lib
# from config.db import async_transaction


class TemplateService:
    """template"""

    def __init__(self, template_dao: TemplateDao):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.template_dao = template_dao or TemplateDao()

    async def add(self, template: TemplateCreate) -> str:
        """新增模板

        :param template: 模板创建数据
        :return: 新建模板的ID
        """
        return await self.template_dao.add(template)

    async def delete(self, id: str):
        """删除指定模板

        :param id: 模板ID
        """
        await self.template_dao.delete(id)

    async def batch_delete(self, batch_delete: TemplateBatchDelete) -> int:
        """批量删除模板

        :param batch_delete: 批量删除请求(含模板ID列表)
        :return: 实际删除数量
        """
        return await self.template_dao.batch_delete(batch_delete.ids)

    async def update(self,template_id: str, template: TemplateUpdate):
        """更新指定模板

        :param template_id: 模板ID
        :param template: 模板更新数据
        """
        await self.template_dao.update(template_id,template)

    async def get(self, id: str) -> Template | None:
        """查询单个模板

        :param id: 模板ID
        :return: 模板对象,未找到返回None
        """
        return await self.template_dao.get(id)
    #
    async def list_paged(self, pagination: PaginationParams):
        """分页查询模板列表

        :param pagination: 分页参数
        :return: 分页响应(数据+总数)
        """
        items = await self.template_dao.list_paged(pagination)
        total = await self.template_dao.count()
        return PaginationResponse.create(items, total,pagination)
    async def get_scroll(self, params: InfiniteScrollParams):
        """滚动加载模板列表(无限滚动场景)

        :param params: 滚动分页参数
        :return: 滚动分页响应(含数据与下一页游标)
        """
        items:list[Template] = await self.template_dao.get_scroll(params)
        return InfiniteScrollResponse.create(items, params.limit)