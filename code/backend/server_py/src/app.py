from common.config import log
from common.config import net
from common.config.index import conf
from common.config.server import app
# # 设置模块搜索路径（支持编译模块和源码模块）
# from tools.nuitka_build.module_loader import setup_module_path
# setup_module_path()

# 主模块
from module_main.controller import static as main_static, status, db, dict_type, dict_item
# # 文件模块(网络文件系统: 虚拟文件树 + local/rustfs/s3 存储无缝切换)
from module_file.controller import filesystem
from module_websearch.controller import websearch
from module_authorization.controller import token, casbin_rule, permission, role, user,auth,dept
# # 业务模块
# from module_template.controller import static,template,template_ex,template_async_learn
# from module_ai.controller import static as ai_static,model_config,llm_base,voice
# # ,ocr 
# from module_dev_tools.controller import template_string
# from module_little_utils.controller import todolist
# # 语言模块
# from module_nlp.controller import synonym
# from module_life.controller import baby_name
# # 知识库模块(项目/文档/成员/部门授权/问答)
from module_rag.controller import (
    conversation,
    project,
    project_document,
    project_document_chunk,
    project_member,
    project_dept,
    rag_chat,
    user_model,
)
# # 知识库模块: 权限声明注册保持权限表与声明一致
from module_rag.config import permissions as rag_permissions  # noqa: F401
# # 博客模块: 目前仅注册权限声明(域 blog),控制器待业务开发后在此导入
from module_blog.config import permissions as blog_permissions  # noqa: F401
# # 地理空间模块(Babylon 地球绘制 + PostGIS 点线面存储)
from module_geometry.controller import feature
from module_geometry.config import permissions as geometry_permissions  # noqa: F401
# # 任务队列模块(Celery+Redis 异步任务: 创建/轮询/取消/重试)
from module_task.controller import task
from module_task.config import permissions as task_permissions  # noqa: F401
# # AI 模块: 仅挂载模型配置管理(用户私有模型配置 + 共享标记),chat/voice/ocr 待启用
from module_ai.controller import model_config, data_clean

if __name__ == "__main__":
    import sys
    import uvicorn
    from common.utils.sys.kill_process import find_and_kill_process

    # Windows 下切换 Selector 事件循环(psycopg 异步模式不支持 ProactorEventLoop)
    if sys.platform == "win32":
        import asyncio

        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # 关闭之前运行的进程
    find_and_kill_process(conf.server.port)
    
    # from fastmcp import FastMCP
    # mcp = FastMCP.from_fastapi(app=app)
    # mcp.run(transport="http", host="127.0.0.1", port=9001)

    # dev启动服务
    uvicorn.run(app, host=conf.server.host, port=conf.server.port)
    # uvicorn.run("src.app:app", host=conf.server.host, port=conf.server.port, reload=True)
