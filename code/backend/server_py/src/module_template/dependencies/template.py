from fastapi import Depends

from module_template.dao.template import TemplateDao
from module_template.service.template import TemplateService

async def get_template_dao() -> TemplateDao:
    """DAO工厂"""
    return TemplateDao()
# 新增的依赖项工厂函数
async def get_template_service(dao: TemplateDao = Depends(get_template_dao)) -> TemplateService:
    """Service工厂"""
    return TemplateService(dao)
