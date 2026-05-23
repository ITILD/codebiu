from common.config import log
from common.config import net
from common.config.index import conf
from common.config.server import app
# # 设置模块搜索路径（支持编译模块和源码模块）
# from tools.nuitka_build.module_loader import setup_module_path
# setup_module_path()

# 主模块
from module_main.controller import static as main_static, status, db, dict_type, dict_item
# # 基础模块
# from module_file.controller import filesystem
# from module_authorization.controller import token, casbin_rule, permission, role, user,auth
# # 业务模块
from module_template.controller import static,template,template_ex,template_async_learn
from module_ai.controller import static as ai_static,model_config,llm_base
# # ,ocr 
# from module_dev_tools.controller import template_string
# from module_little_utils.controller import todolist
# # 语言模块
# from module_nlp.controller import synonym
# from module_life.controller import baby_name
import logging
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    import uvicorn
    from common.utils.sys.kill_process import find_and_kill_process

    # 关闭之前运行的进程
    find_and_kill_process(conf.server.port)
    
    from fastmcp import FastMCP
    mcp = FastMCP.from_fastapi(app=app)
    mcp.run(transport="http", host="127.0.0.1", port=9001)


    # dev启动服务
    uvicorn.run(app, host=conf.server.host, port=conf.server.port)
    # uvicorn.run("src.app:app", host=conf.server.host, port=conf.server.port, reload=True)
