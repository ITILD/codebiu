# casbin_config.py
"""
Casbin 权限统一配置

域(dom)划分约定:
    "*"     全局域,系统管理员使用,可穿透所有子模块
    "sys"   授权模块域(用户/角色/部门/权限/策略规则管理)
    "main"  主模块域(字典/状态/数据库/文件/搜索等基础资源)
    "rag"   知识库模块域(项目列表等模块级资源)
    "blog"  博客模块域

角色体系(两级内置角色):
    admin  全局管理员,策略 ("admin","*","*","*") 穿透一切
    user   普通用户,策略由各模块 default_policies 声明合并而来
    其余角色由管理员在界面自建(见 role 表),项目级权限不走 casbin

各子模块的默认策略由模块自己声明:
    模块在自身 config/permissions.py 中定义 ModulePermissionDefine 并注册到
    permission_registry(见 registry.py),启动时此处统一幂等写入 casbin,
    并同步 role/permission 两张表(供前端管理界面使用)。
"""
import casbin
from casbin_async_sqlalchemy_adapter import Adapter, CasbinRule
from common.config.db import db_rel
import logging

logger = logging.getLogger(__name__)

# 内置角色(role 表中始终存在,策略随声明维护,不可删除)
BUILTIN_ROLES: list[dict] = [
    {
        "name": "系统管理员",
        "role_key": "admin",
        "description": "全局管理员,拥有系统全部权限",
        "sort": 1,
    },
    {
        "name": "普通用户",
        "role_key": "user",
        "description": "新注册用户默认角色,拥有各模块声明的基础权限",
        "sort": 2,
    },
]


class AuthManager:
    """权限管理器"""

    def __init__(self):
        self.enforcer: casbin.AsyncEnforcer | None = None

    async def init_default_casbin(self) -> casbin.AsyncEnforcer | None:
        """
        幂等初始化默认策略(重复启动安全,零冗余写入),并同步角色/权限表
        :return: 初始化后的 enforcer,失败返回 None
        """
        if self.enforcer:
            return self.enforcer
        try:
            # 触发基础权限(sys/main 域)注册;业务模块(rag/blog...)的声明
            # 已在 app.py 导入各模块时完成注册
            from module_authorization.config.module_permissions import (
                SYS_DEFINE,
                MAIN_DEFINE,
            )
            from module_authorization.config.registry import permission_registry

            casbin_path = "rbac_model.conf"
            # 直接将 engine 对象传递给sqlalchemy数据库Adapter,并指定使用自定义的CasbinRule模型
            adapter = Adapter(db_rel.engine, CasbinRule)
            # 如果没有表则创建表
            await adapter.create_table()

            # 初始化 Casbin enforcer
            enforcer = casbin.AsyncEnforcer(casbin_path, adapter)
            # 加载策略
            await enforcer.load_policy()

            # 关闭逐条落盘,批量提交优化性能
            enforcer.enable_auto_save(False)

            # ===== 批量查缺: 一次拉取现有策略,内存中计算缺失集合 =====
            # 注: get_policy 是同步方法(返回list),不能 await
            existing: set[tuple] = {tuple(p) for p in enforcer.get_policy()}

            # 期望的默认策略集合
            expected: set[tuple[str, str, str, str]] = set()

            # 全局策略: 超管角色拥有所有域所有资源的所有动作
            expected.add(("admin", "*", "*", "*"))

            # 内置 user 角色策略: 各模块声明的新用户默认权限合并而来
            for dom, obj, act in permission_registry.default_user_policies():
                expected.add(("user", dom, obj, act))

            # 缺失部分一次性批量写入(add_policies 为异步批量接口)
            missing = sorted(expected - existing)
            if missing:
                await enforcer.add_policies([list(rule) for rule in missing])
                await enforcer.save_policy()
                logger.info(f"策略批量初始化完成,新增 {len(missing)} 条")
            else:
                logger.info("默认权限策略完整,无需补写")

            # 恢复自动落盘:运行期通过API增删的策略/角色实时持久化
            enforcer.enable_auto_save(True)

            self.enforcer = enforcer

            # 同步角色表/权限表(独立事务,失败不影响 casbin)
            try:
                await self.sync_permission_tables()
            except Exception as e:
                logger.error(f"同步角色/权限表失败: {e}")

            modules = [d.module for d in permission_registry.get_all()]
            logger.info(f"已注册权限声明模块: {modules}(基础: {SYS_DEFINE.module}/{MAIN_DEFINE.module})")
            return enforcer
        except Exception as e:
            logger.error(f"初始化默认权限策略失败: {e}")
            return None

    async def sync_permission_tables(self) -> None:
        """
        将注册中心的声明幂等同步到 role 表与 permission 表
        - role 表: upsert 内置角色(admin/user),不动 data_scope/is_active 等用户可编辑字段
        - permission 表: 按 code upsert,声明字段以模块声明为准(模块权限由模块代码负责)
        - 优化: 已存在且声明字段无变化的记录跳过写库,避免每次启动全量 UPDATE
        """
        from module_authorization.config.registry import permission_registry
        from module_authorization.dao.role import RoleDao
        from module_authorization.dao.permission import PermissionDao
        from module_authorization.do.role import RoleCreate, RoleUpdate
        from module_authorization.do.permission import PermissionCreate, PermissionUpdate

        role_dao = RoleDao()
        perm_dao = PermissionDao()
        # 统计: 本次启动实际新增/更新的记录数
        stats = {"added": 0, "updated": 0, "skipped": 0}

        async def _upsert_role(role: dict) -> None:
            """按 role_key 幂等写入角色表(声明字段无变化时跳过)"""
            existing = await role_dao.get_by_role_key(role["role_key"])
            if existing:
                # 仅声明管理的字段参与变化检测
                changed = (
                    existing.name != role["name"]
                    or existing.description != role["description"]
                    or existing.sort != role["sort"]
                )
                if changed:
                    await role_dao.update(
                        existing.id,
                        RoleUpdate(
                            name=role["name"],
                            description=role["description"],
                            sort=role["sort"],
                        ),
                    )
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
            else:
                await role_dao.add(RoleCreate(**role))
                stats["added"] += 1

        async def _upsert_perm(data: dict) -> str:
            """按 code 幂等写入权限表,返回记录ID(声明字段无变化时跳过)"""
            existing = await perm_dao.get_by_code(data["code"])
            if existing:
                changed = any(
                    getattr(existing, k, None) != v for k, v in data.items()
                )
                if changed:
                    await perm_dao.update(existing.id, PermissionUpdate(**data))
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
                return existing.id
            stats["added"] += 1
            return await perm_dao.add(PermissionCreate(**data))

        # 角色表同步: 内置角色(admin/user)
        for role in BUILTIN_ROLES:
            await _upsert_role(role)

        for define in permission_registry.get_all():
            # 权限表同步: 模块根节点(M目录)
            root_id = await _upsert_perm(
                {
                    "name": define.name,
                    "code": define.module,
                    "menu_type": "M",
                    "description": define.description,
                    "icon": define.icon,
                    "order_num": define.order_num,
                    "parent_id": "0",
                }
            )

            # 权限表同步: 递归同步模块子树
            async def _sync_children(nodes, parent_id: str) -> None:
                for node in nodes:
                    node_id = await _upsert_perm(
                        {
                            "name": node.name,
                            "code": node.code,
                            "menu_type": node.menu_type,
                            "description": node.description,
                            "path": node.path,
                            "icon": node.icon,
                            "order_num": node.order_num,
                            "visible": node.visible,
                            "parent_id": parent_id,
                        }
                    )
                    if node.children:
                        await _sync_children(node.children, node_id)

            await _sync_children(define.nodes, root_id)

        logger.info(
            f"角色表/权限表声明同步完成: 新增 {stats['added']}, "
            f"更新 {stats['updated']}, 无变化跳过 {stats['skipped']}"
        )


auth_manager = AuthManager()
