from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from common.config.path import DIR_PUBLIC
from module_template.config.server import module_app

# 静态配置
DIR_HTML_TEMPLATE = DIR_PUBLIC / "ai"
############################### 静态首页 ##############################################
# html path 当前ip端口html路径


html_file = open(DIR_HTML_TEMPLATE / "index.html", "r", encoding="utf-8").read()
router = APIRouter()


# 首页 app非router挂载
@router.get("/", response_class=HTMLResponse, summary="server首页html")
async def server():
    return html_file


# 配置前端静态文件服务
module_app.mount(
    "/static",
    StaticFiles(directory=DIR_HTML_TEMPLATE, html=True),
    name="assets",
)

module_app.include_router(router, prefix="/static", tags=["template_static"])
