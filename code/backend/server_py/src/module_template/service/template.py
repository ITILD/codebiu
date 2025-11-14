# self
from common.utils.db.schema.pagination import InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse
from module_template.do.template import Template, TemplateCreate, TemplateUpdate
from module_template.dao.template import TemplateDao

# lib
# from config.db import async_transaction


class TemplateService:
    """template"""

    def __init__(self, template_dao: TemplateDao):
        self.template_dao = template_dao or TemplateDao()

    async def add(self, template: TemplateCreate) -> str:
        return await self.template_dao.add(template)

    async def delete(self, id: str):
        await self.template_dao.delete(id)

    async def update(self,template_id: str, template: TemplateUpdate):
        await self.template_dao.update(template_id,template)

    async def get(self, id: str) -> Template | None:
        return await self.template_dao.get(id)
    # 
    async def list(self, pagination: PaginationParams):
        items = await self.template_dao.list(pagination)
        total = await self.template_dao.count()
        return PaginationResponse.create(items, total,pagination)
    async def get_scroll(self, params: InfiniteScrollParams):

        items:list[Template] = await self.template_dao.get_scroll(params)
        return InfiniteScrollResponse.create(items, params.limit)