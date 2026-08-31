from common.config.server import app
from fastapi import FastAPI
import logging

# 导入即注册本模块权限声明到权限中心(rag 域)
from module_rag.config import permissions as rag_permissions  # noqa: F401
# 导入即注册本模块字典种子到字典中心(rag 域,与代码枚举对齐)
from module_rag.config import dict_seed as rag_dict_seed  # noqa: F401

logger = logging.getLogger(__name__)

module_app = FastAPI()

app.mount("/rag", module_app)

logger.info("module_rag服务配置完成")
