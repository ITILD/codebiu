# casbin_config.py
import casbin
from casbin_async_sqlalchemy_adapter import Adapter
from common.config.db import db_rel
from module_authorization.do.casbin_rule import CasbinRule
import logging
logger = logging.getLogger(__name__)

casbin_path = "rbac_model.conf"
# 直接将 engine 对象传递给sqlalchemy数据库Adapter，并指定使用自定义的CasbinRule模型
adapter = Adapter(db_rel.engine, CasbinRule) 

# 初始化 Casbin enforcer
enforcer = casbin.AsyncEnforcer(casbin_path, adapter)
