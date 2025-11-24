"""
模板字符串依赖注入配置
"""

from fastapi import Depends
from module_dev_tools.dao.template_string import TemplateStringDao
from module_dev_tools.service.template_string import TemplateStringService


async def get_template_string_dao() -> TemplateStringDao:
    """
    DAO工厂函数
    :return: TemplateStringDao实例
    """
    return TemplateStringDao()


async def get_template_string_service(
    dao: TemplateStringDao = Depends(get_template_string_dao)
) -> TemplateStringService:
    """
    Service工厂函数
    :param dao: DAO依赖注入
    :return: TemplateStringService实例
    """
    return TemplateStringService(dao)