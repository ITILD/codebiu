from common.config.server import app
from common.config.lifespan import register_init_hook
# lib
from fastapi import FastAPI
import logging
# # 引入权限中间件
# from common.middleware.permission import PermissionMiddleware
# # 添加权限中间件
# app.add_middleware(PermissionMiddleware)

logger = logging.getLogger(__name__)

module_app = FastAPI()

app.mount("/authorization", module_app)


@register_init_hook
async def init_casbin_policy():
    """幂等初始化 casbin 默认策略并同步角色/权限表(须先于管理员引导)"""
    # 延迟导入避免循环依赖
    from module_authorization.config.casbin_rule import auth_manager
    await auth_manager.init_default_casbin()
    logger.info("Casbin policy init successfully.")


@register_init_hook
async def bootstrap_default_admin():
    """幂等创建/修复默认管理员账户(依赖 casbin enforcer 已初始化)"""
    # 延迟导入避免循环依赖
    from module_authorization.config.admin import ensure_default_admin
    await ensure_default_admin()
    logger.info("Default admin bootstrap successfully.")


logger.info("module_authorization服务配置完成")