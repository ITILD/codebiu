from common.config import log  # noqa: F401
from common.config import net  # noqa: F401
from common.config.index import conf
from common.config.server import app

# 引入路由
from module_template.controller import static,template,template_ex,template_test  # noqa: F401
from module_ai.controller import static as ai_static,model_config,llm_base,ocr,translate  # noqa: F401
from module_file.controller import file  # noqa: F401
from module_main.controller import static as main_static, status, db  # noqa: F401
from module_authorization.controller import token, casbin_rule, permission, role, user,auth  # noqa: F401

import logging
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    import uvicorn
    from common.utils.sys.kill_process import find_and_kill_process

    # 关闭之前运行的进程
    find_and_kill_process(conf.server.port)

    # dev启动服务
    uvicorn.run(app, host=conf.server.host, port=conf.server.port)
