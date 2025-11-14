from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from common.config.path import DIR_PUBLIC
from common.config.server import app, SERVER_ROOT_PATH

from common.utils.fastapiEX.swagger_ex import swagger_local

# lib
import logging

logger = logging.getLogger(__name__)


# 静态配置
DIR_HTML_MAIN = DIR_PUBLIC / "main"
############################### 静态首页 ##############################################
# html path 当前ip端口html路径
router = APIRouter()

@app.get(
    "/",
    response_class=HTMLResponse,
    summary="server首页html",
    tags=["main_html"],
    description="返回首页html",
)
async def server():
    html_file = open(DIR_HTML_MAIN / "index.html", "r", encoding="utf-8").read()
    return html_file


app.mount(
    "/static",
    StaticFiles(directory=DIR_HTML_MAIN, html=True),
)
# 配置前端静态文件服务
app.mount(
    "/common",
    StaticFiles(directory=DIR_PUBLIC / "common"),
)

# 自定义 Swagger
swagger_local(
    swagger_js_url=SERVER_ROOT_PATH
    + "/common/assets/js/swagger-ui/swagger-ui-bundle.js",
    swagger_css_url=SERVER_ROOT_PATH + "/common/assets/js/swagger-ui/swagger-ui.css",
)
