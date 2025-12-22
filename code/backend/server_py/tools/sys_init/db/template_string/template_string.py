#  用validate_template_syntax 初始化数据
import aiofiles
from common.config.index import conf
from module_dev_tools.service.template_string import TemplateStringService
from module_dev_tools.do.template_string import TemplateStringCreate


async def main():
    model_config_service = TemplateStringService()
    # 异步打开文件读取内容
    async with aiofiles.open(r'tools\sys_init\db\template_string\template_controller.txt', mode='r', encoding='utf-8') as f:
        template_content = await f.read()
    
        template_string: TemplateStringCreate = TemplateStringCreate(
            name="controller模板",
            description="controller模板自动生成",
            template_content=template_content,
            category="dev",
        )
        await model_config_service.add(template_string)
    # 异步打开文件读取内容
    async with aiofiles.open(r'tools\sys_init\db\template_string\template_service.txt', mode='r', encoding='utf-8') as f:
        template_content = await f.read()
    
        template_string: TemplateStringCreate = TemplateStringCreate(
            name="service模板",
            description="service模板自动生成",
            template_content=template_content,
            category="dev",
        )
        await model_config_service.add(template_string)
    # 异步打开文件读取内容
    async with aiofiles.open(r'tools\sys_init\db\template_string\template_dependencies.txt', mode='r', encoding='utf-8') as f:
        template_content = await f.read()
    
        template_string: TemplateStringCreate = TemplateStringCreate(
            name="dependencies模板",
            description="dependencies模板自动生成",
            template_content=template_content,
            category="dev",
        )
        await model_config_service.add(template_string)
    # 异步打开文件读取内容
    async with aiofiles.open(r'tools\sys_init\db\template_string\template_do.txt', mode='r', encoding='utf-8') as f:
        template_content = await f.read()
    
        template_string: TemplateStringCreate = TemplateStringCreate(
            name="controller模板",
            description="controller模板自动生成",
            template_content=template_content,
            category="dev",
        )
        await model_config_service.add(template_string)
    # 异步打开文件读取内容
    async with aiofiles.open(r'tools\sys_init\db\template_string\template_dao.txt', mode='r', encoding='utf-8') as f:
        template_content = await f.read()
    
        template_string: TemplateStringCreate = TemplateStringCreate(
            name="dao模板",
            description="dao模板自动生成",
            template_content=template_content,
            category="dev",
        )
        await model_config_service.add(template_string)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
