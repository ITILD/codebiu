"""
module_site 权限声明(个人小站模块自治声明本模块涉及的权限)

三条业务线:
    blog    博客(在线 markdown 编辑/关联 URL 发布展示)
    memo    备忘(备忘编辑管理 + 日历展示, 承接原 module_little_utils 的 todolist)
    ledger  记账(收支记录与图表统计)

修改本模块权限只需编辑本文件, 重启后自动幂等同步 casbin 与权限表。
"""
from module_authorization.config.registry import (
    ModulePermissionDefine,
    PermNode,
    permission_registry,
)

SITE_DEFINE = ModulePermissionDefine(
    module="site",
    name="个人小站",
    icon="Notebook",
    order_num=25,
    description="个人小站: 博客发布/备忘管理/记账本",
    nodes=[
        PermNode(
            name="博客",
            code="site:blog",
            menu_type="C",
            path="/site/blog",
            order_num=1,
            children=[
                PermNode(name="查询", code="site:blog:read", menu_type="F"),
                PermNode(name="发布", code="site:blog:create", menu_type="F"),
                PermNode(name="修改", code="site:blog:update", menu_type="F"),
                PermNode(name="删除", code="site:blog:delete", menu_type="F"),
            ],
        ),
        PermNode(
            name="备忘",
            code="site:memo",
            menu_type="C",
            path="/site/memo",
            order_num=2,
            children=[
                PermNode(name="查询", code="site:memo:read", menu_type="F"),
                PermNode(name="新增", code="site:memo:create", menu_type="F"),
                PermNode(name="修改", code="site:memo:update", menu_type="F"),
                PermNode(name="删除", code="site:memo:delete", menu_type="F"),
            ],
        ),
        PermNode(
            name="记账",
            code="site:ledger",
            menu_type="C",
            path="/site/ledger",
            order_num=3,
            children=[
                PermNode(name="查询", code="site:ledger:read", menu_type="F"),
                PermNode(name="新增", code="site:ledger:create", menu_type="F"),
                PermNode(name="修改", code="site:ledger:update", menu_type="F"),
                PermNode(name="删除", code="site:ledger:delete", menu_type="F"),
            ],
        ),
    ],
    # 默认新模块不带权限(default_policies=[]):
    # 普通用户需管理员在 角色管理→分配权限 中按需勾选本模块权限码
    default_policies=[],
)

# 注册到权限中心(app 导入本模块 config 时生效)
permission_registry.register(SITE_DEFINE)
