from common.config import log
from common.config import net
from common.config.index import conf
from common.config.server import app
# 主模块
from module_main.controller import static as main_static, status, db
# # 基础模块
# from module_file.controller import filesystem
# from module_authorization.controller import token, casbin_rule, permission, role, user,auth
# # 业务模块
# from module_template.controller import static,template,template_ex,template_async_learn
# from module_ai.controller import static as ai_static,model_config,llm_base
# # ,ocr 
# from module_dev_tools.controller import template_string
# from module_little_utils.controller import todolist
# 
import logging
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    import uvicorn
    from common.utils.sys.kill_process import find_and_kill_process

    # 关闭之前运行的进程
    find_and_kill_process(conf.server.port)

    # dev启动服务
    uvicorn.run(app, host=conf.server.host, port=conf.server.port)
    # uvicorn.run("src.app:app", host=conf.server.host, port=conf.server.port, reload=True)
