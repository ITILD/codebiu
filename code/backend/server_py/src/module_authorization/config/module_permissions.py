"""
module_authorization 基础权限声明

负责系统级基础权限:
    sys  域: 授权模块自身的管理资源(用户/角色/部门/权限/策略规则)
    main 域: 系统基础资源(字典/数据库/文件/网页搜索)

角色说明: 不再声明模块预设角色,全局仅 admin/user 两个内置角色
(见 registry.py 说明);需要细分角色由管理员在界面自建。

业务模块(rag/blog/...)不要在此添加权限,
请在各自模块的 config/permissions.py 中声明并注册(参见 registry.py 说明)。
"""
from module_authorization.config.registry import (
    ModulePermissionDefine,
    PermNode,
    permission_registry,
)


def _crud_nodes(obj: str, name: str, path: str | None = None, icon: str | None = None,
                order: int = 0) -> PermNode:
    """快速构造带增删改查按钮的菜单节点"""
    return PermNode(
        name=name,
        code=f"sys:{obj}",
        menu_type="C",
        path=path,
        icon=icon,
        order_num=order,
        children=[
            PermNode(name="查询", code=f"sys:{obj}:read", menu_type="F", order_num=1),
            PermNode(name="新增", code=f"sys:{obj}:create", menu_type="F", order_num=2),
            PermNode(name="修改", code=f"sys:{obj}:update", menu_type="F", order_num=3),
            PermNode(name="删除", code=f"sys:{obj}:delete", menu_type="F", order_num=4),
        ],
    )


# ---------------- sys 域: 授权模块自身管理 ----------------
SYS_DEFINE = ModulePermissionDefine(
    module="sys",
    name="系统管理",
    icon="Monitor",
    order_num=1,
    description="用户/角色/部门/权限/策略规则等系统基础管理",
    nodes=[
        _crud_nodes("user", "用户管理", path="/_sys/manager/user", icon="UserFilled", order=1),
        _crud_nodes("role", "角色管理", path="/_sys/manager/role", icon="Avatar", order=2),
        _crud_nodes("dept", "部门管理", path="/_sys/manager/dept", icon="OfficeBuilding", order=3),
        _crud_nodes("permission", "权限管理", path="/_sys/manager/permission", icon="Key", order=4),
        _crud_nodes("casbin", "策略规则", path="/_sys/manager/casbin", icon="List", order=5),
    ],
    # 新用户不自动获得系统管理权限,需管理员分配
    default_policies=[],
)

# ---------------- main 域: 系统基础资源 ----------------
MAIN_DEFINE = ModulePermissionDefine(
    module="main",
    name="基础资源",
    icon="Files",
    order_num=2,
    description="字典/数据库/虚拟文件系统/网页搜索等系统基础资源",
    nodes=[
        PermNode(
            name="字典管理",
            code="main:dict",
            menu_type="C",
            path="/_sys/database/dict",
            icon="Notebook",
            order_num=1,
            children=[
                PermNode(name="查询", code="main:dict:read", menu_type="F"),
                PermNode(name="新增", code="main:dict:create", menu_type="F"),
                PermNode(name="修改", code="main:dict:update", menu_type="F"),
                PermNode(name="删除", code="main:dict:delete", menu_type="F"),
            ],
        ),
        PermNode(
            name="数据库管理",
            code="main:db",
            menu_type="C",
            path="/_sys/database/overview",
            icon="Coin",
            order_num=2,
            children=[PermNode(name="查询", code="main:db:read", menu_type="F")],
        ),
        PermNode(
            name="文件管理",
            code="main:file",
            menu_type="C",
            path="/_sys/file",
            icon="FolderOpened",
            order_num=3,
            children=[
                PermNode(name="浏览/下载", code="main:file:read", menu_type="F"),
                PermNode(name="上传/新建", code="main:file:create", menu_type="F"),
                PermNode(name="重命名/移动", code="main:file:update", menu_type="F"),
                PermNode(name="删除", code="main:file:delete", menu_type="F"),
            ],
        ),
        PermNode(
            name="网页搜索",
            code="main:search",
            menu_type="C",
            icon="Search",
            order_num=4,
            children=[PermNode(name="使用", code="main:search:read", menu_type="F")],
        ),
    ],
    # 新注册用户默认拥有基础资源只读权限(main 域)
    default_policies=[
        ("main", "*", "read"),
    ],
)

# 注册基础权限声明
permission_registry.register(SYS_DEFINE)
permission_registry.register(MAIN_DEFINE)
