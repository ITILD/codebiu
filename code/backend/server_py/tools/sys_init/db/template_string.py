#  用validate_template_syntax 初始化数据
from common.config.index import conf
from module_dev_tools.service.template_string import TemplateStringService
from module_dev_tools.do.template_string import TemplateStringCreate



async def main():
    model_config_service = TemplateStringService()
    template_string: TemplateStringCreate = TemplateStringCreate(
        name="controller模板",
        description = "controller模板自动生成",
        template_content="test ${username}测试",
        category="dev"
    )
    await model_config_service.add(template_string)
    
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())