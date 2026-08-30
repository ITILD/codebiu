# casbin_config.py
"""
Casbin 权限统一配置

域(dom)划分约定:
    "*"              全局域,系统管理员使用,可穿透所有子模块
    "main"           主模块域(字典/状态/数据库管理等基础资源)
    "rag"            知识库模块全局域(项目列表等模块级资源)
    "rag:{proj_id}"  具体知识库项目域,实现同知识库多用户隔离

各子模块默认策略独立声明于 MODULE_POLICY_PRESETS,启动时幂等写入。
"""
import casbin
from casbin_async_sqlalchemy_adapter import Adapter, CasbinRule
from common.config.db import db_rel
import logging

logger = logging.getLogger(__name__)


class ModulePolicyPreset:
    """子模块默认策略预设(角色, 域, 资源, 动作列表)"""

    def __init__(self, module: str, rules: list[tuple[str, str, str, str]]):
        self.module = module
        self.rules = rules


# ---------------- 子模块策略预设 ----------------

# 主模块: 基础资源(字典/状态/数据库/文件)
MAIN_POLICY_PRESET = ModulePolicyPreset(
    module="main",
    rules=[
        # 主模块管理员: 全部基础资源读写
        ("main_admin", "main", "*", "read|create|update|delete"),
        # 主模块运维: 可读写不可删
        ("main_operator", "main", "*", "read|create|update"),
        # 主模块访客: 只读
        ("main_viewer", "main", "*", "read"),
        # ---- 文件子模块(虚拟文件系统)独立策略 ----
        # 管理员: 文件全权限
        ("main_admin", "main", "file", "read|create|update|delete"),
        # 运维: 可上传/重命名/移动,不可删除
        ("main_operator", "main", "file", "read|create|update"),
        # 访客: 仅浏览与下载
        ("main_viewer", "main", "file", "read"),
        # ---- 网页搜索子模块(websearch)独立策略 ----
        # 搜索为只读代理能力,全部角色仅授予 read
        ("main_admin", "main", "search", "read"),
        ("main_operator", "main", "search", "read"),
        ("main_viewer", "main", "search", "read"),
    ],
)

# 知识库模块: 模块级资源(项目列表/文档/成员/对话)
RAG_POLICY_PRESET = ModulePolicyPreset(
    module="rag",
    rules=[
        # 知识库管理员: 模块内全部资源
        ("rag_admin", "rag", "*", "read|create|update|delete|manage"),
        # 普通用户默认角色: 可创建个人知识库并对话(项目级访问由成员关系控制)
        ("rag_user", "rag", "project", "read|create"),
        ("rag_user", "rag", "chat", "read|write"),
        # 项目管理员: 项目/文档/成员/对话可管理
        ("project_admin", "rag", "project", "read|update|delete|manage"),
        ("project_admin", "rag", "doc", "read|upload|update|delete"),
        ("project_admin", "rag", "member", "read|invite|update|remove"),
        ("project_admin", "rag", "chat", "read|write"),
        # 项目编辑: 可读写文档与对话,不可管理成员
        ("project_editor", "rag", "project", "read"),
        ("project_editor", "rag", "doc", "read|upload|update"),
        ("project_editor", "rag", "member", "read"),
        ("project_editor", "rag", "chat", "read|write"),
        # 项目只读: 仅可读
        ("project_reader", "rag", "project", "read"),
        ("project_reader", "rag", "doc", "read"),
        ("project_reader", "rag", "member", "read"),
        ("project_reader", "rag", "chat", "read"),
    ],
)

# 全部子模块预设注册表(新增模块在此追加)
MODULE_POLICY_PRESETS: list[ModulePolicyPreset] = [
    MAIN_POLICY_PRESET,
    RAG_POLICY_PRESET,
]


class AuthManager:
    """权限管理器"""

    def __init__(self):
        self.enforcer: casbin.AsyncEnforcer | None = None

    async def init_default_casbin(self) -> casbin.AsyncEnforcer | None:
        """幂等初始化默认策略(重复启动安全,零冗余写入),如果集合已存在则log警告并返回"""
        if self.enforcer:
            return self.enforcer
        try:
            casbin_path = "rbac_model.conf"
            # 直接将 engine 对象传递给sqlalchemy数据库Adapter,并指定使用自定义的CasbinRule模型
            adapter = Adapter(db_rel.engine, CasbinRule)
            # 如果没有表则创建表
            await adapter.create_table()

            # 初始化 Casbin enforcer
            enforcer = casbin.AsyncEnforcer(casbin_path, adapter)
            # 加载策略
            await enforcer.load_policy()

            # 全局策略: 超管角色拥有所有域所有资源的所有动作
            global_rules = [("admin", "*", "*", "*")]

            # 关闭逐条落盘,批量提交优化性能
            enforcer.enable_auto_save(False)
            added_count = 0

            for role, dom, obj, acts in global_rules:
                for act in acts.split("|"):
                    if not enforcer.has_policy(role, dom, obj, act):
                        await enforcer.add_policy(role, dom, obj, act)
                        added_count += 1

            # 各子模块默认策略
            for preset in MODULE_POLICY_PRESETS:
                for role, dom, obj, acts in preset.rules:
                    for act in acts.split("|"):
                        if not enforcer.has_policy(role, dom, obj, act):
                            await enforcer.add_policy(role, dom, obj, act)
                            added_count += 1

            if added_count > 0:
                await enforcer.save_policy()
                logger.info(f"策略初始化完成,新增 {added_count} 条")
            else:
                logger.warning("默认权限策略已存在,跳过初始化")

            # 恢复自动落盘:运行期通过API增删的策略/角色实时持久化
            enforcer.enable_auto_save(True)

            self.enforcer = enforcer
            return enforcer
        except Exception as e:
            logger.error(f"初始化默认权限策略失败: {e}")
            return None


auth_manager = AuthManager()
