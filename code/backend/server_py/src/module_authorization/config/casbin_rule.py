# casbin_config.py
import casbin
from casbin_async_sqlalchemy_adapter import Adapter,CasbinRule
# from sqlalchemy.orm import sessionmaker
from common.config.db import db_rel
import logging

logger = logging.getLogger(__name__)

class AuthManager:
    """权限管理器"""

    def __init__(self):
        self.enforcer: casbin.AsyncEnforcer | None = None
        
    async def init_default_casbin(self) -> casbin.AsyncEnforcer:
        """幂等初始化默认策略（重复启动安全，零冗余写入）,如果集合已存在则log警告并返回"""
        if self.enforcer:
            return self.enforcer
        try:

            casbin_path = "rbac_model.conf"
            # 直接将 engine 对象传递给sqlalchemy数据库Adapter，并指定使用自定义的CasbinRule模型
            adapter = Adapter(db_rel.engine, CasbinRule)
            # 如果没有表则创建表
            await adapter.create_table()

            # 初始化 Casbin enforcer
            enforcer = casbin.AsyncEnforcer(casbin_path, adapter)
            # 加载策略
            await enforcer.load_policy()
            
            # 默认系统管理员角色
            default_admin_role = "admin"
            policy_rules = [
                # 超管模板：拥有所有对象的所有动作权限
                (default_admin_role, "*", "*", "*"),
                # 知识库权限
                ("project_admin", "*", "project", "read|update|delete|manage"),
                ("project_admin", "*", "doc", "read|upload|update|delete"),
                ("reader", "*", "project", "read"),
                ("reader", "*", "doc", "read"),
                ("reader", "knowledge", "doc", "read"),
                # 聊天
            ]
            # 关闭逐条落盘，批量提交优化性能
            enforcer.enable_auto_save(False)
            added_count = 0

            for role, dom, obj, acts in policy_rules:
                for act in acts.split("|"):
                    if not enforcer.has_policy(role, dom, obj, act):
                        await enforcer.add_policy(role, dom, obj, act)
                        added_count += 1

            if added_count > 0:
                await enforcer.save_policy()
                logger.info(f"策略初始化完成，新增 {added_count} 条")
            else:
                logger.warning("默认权限策略已存在，跳过初始化")
                
            self.enforcer = enforcer
            return enforcer
        except Exception as e:
            logger.error(f"初始化默认权限策略失败: {e}")
            return None


auth_manager = AuthManager()