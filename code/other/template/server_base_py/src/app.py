from common.config import log  # noqa: F401
from common.config.index import conf
from common.config.server import app  # noqa: F401
# 引入路由
from module_main.contoller import index
import logging

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host=conf.server.host,
        port=conf.server.port,
        reload=True
    )
