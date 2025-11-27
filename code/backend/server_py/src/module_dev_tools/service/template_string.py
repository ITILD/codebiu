"""
模板字符串服务层
提供模板管理和渲染功能
"""

from string import Template
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    InfiniteScrollResponse,
    PaginationParams,
    PaginationResponse,
)
from module_dev_tools.do.template_string import (
    TemplateString,
    TemplateStringCreate,
    TemplateStringUpdate,
    TemplateRenderRequest,
    TemplateRenderResponse,
)
from module_dev_tools.dao.template_string import TemplateStringDao


class TemplateStringService:
    """
    模板字符串服务
    """

    def __init__(self, template_string_dao: TemplateStringDao):
        self.template_string_dao = template_string_dao or TemplateStringDao()

    async def add(self, template_string: TemplateStringCreate) -> str:
        """
        创建新模板字符串
        :param template_string: 模板字符串创建数据
        :return: 创建的模板字符串ID
        """
        return await self.template_string_dao.add(template_string)

    async def delete(self, id: str) -> None:
        """
        删除模板字符串
        :param id: 模板字符串ID
        """
        await self.template_string_dao.delete(id)

    async def update(self, template_string_id: str, template_string: TemplateStringUpdate) -> None:
        """
        更新模板字符串
        :param template_string_id: 模板字符串ID
        :param template_string: 模板字符串更新数据
        """
        await self.template_string_dao.update(template_string_id, template_string)

    async def get(self, id: str) -> TemplateString | None:
        """
        获取单个模板字符串
        :param id: 模板字符串ID
        :return: 模板字符串对象
        """
        return await self.template_string_dao.get(id)

    async def list_all(self, pagination: PaginationParams) -> PaginationResponse:
        """
        分页查询模板字符串列表
        :param pagination: 分页参数
        :return: 分页响应结果
        """
        items = await self.template_string_dao.list_all(pagination)
        total = await self.template_string_dao.count()
        return PaginationResponse.create(items, total, pagination)

    async def get_scroll(self, params: InfiniteScrollParams) -> InfiniteScrollResponse:
        """
        无限滚动分页查询
        :param params: 滚动参数
        :return: 滚动响应结果
        """
        items = await self.template_string_dao.get_scroll(params)
        return InfiniteScrollResponse.create(items, params.limit)

    async def render_template(self, render_request: TemplateRenderRequest) -> TemplateRenderResponse:
        """
        渲染模板
        :param render_request: 渲染请求
        :return: 渲染响应
        """
        template_content = render_request.template_content
        template_id = render_request.template_id
        
        # 如果提供了模板ID，从数据库获取模板内容
        if template_id and not template_content:
            template = await self.template_string_dao.get(template_id)
            if not template:
                raise ValueError(f"未找到ID为 {template_id} 的模板")
            template_content = template.template_content
        elif not template_content:
            raise ValueError("必须提供模板ID或模板内容")
        
        # 使用string.Template进行模板渲染
        template_obj = Template(template_content)
        
        # 提取模板中的变量
        template_variables = self._extract_template_variables(template_content)
        
        # 检查变量是否完整
        variables_used = []
        variables_missing = []
        
        for var in template_variables:
            if var in render_request.variables:
                variables_used.append(var)
            else:
                variables_missing.append(var)
        
        # 渲染模板（即使有缺失变量也尝试渲染）
        try:
            rendered_content = template_obj.safe_substitute(render_request.variables)
        except Exception as e:
            raise ValueError(f"模板渲染失败: {str(e)}")
        
        return TemplateRenderResponse(
            rendered_content=rendered_content,
            template_id=template_id,
            variables_used=variables_used,
            variables_missing=variables_missing
        )

    async def get_by_category(self, category: str) -> list:
        """
        根据分类查询模板字符串
        :param category: 分类名称
        :return: 模板字符串列表
        """
        return await self.template_string_dao.get_by_category(category)



    def _extract_template_variables(self, template_content: str) -> list:
        """
        从模板内容中提取变量名
        :param template_content: 模板内容
        :return: 变量名列表
        """
        import re
        # 匹配 ${variable} 格式的变量
        pattern = r'\$\{([^}]+)\}'
        variables = re.findall(pattern, template_content)
        return list(set(variables))  # 去重

    async def validate_template_syntax(self, template_content: str) -> dict:
        """
        验证模板语法
        :param template_content: 模板内容
        :return: 验证结果
        """
        try:
            Template(template_content)
            variables = self._extract_template_variables(template_content)
            return {
                "valid": True,
                "variables": variables,
                "message": "模板语法正确"
            }
        except Exception as e:
            return {
                "valid": False,
                "variables": [],
                "message": f"模板语法错误: {str(e)}"
            }