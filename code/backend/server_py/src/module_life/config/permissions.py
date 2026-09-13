"""
module_life 权限声明(生活工具模块自治声明本模块涉及的权限)

业务线:
    baby_name  宝宝取名(参考体系严格推算 + AI 流式起名)

修改本模块权限只需编辑本文件, 重启后自动幂等同步 casbin 与权限表。
"""
from module_authorization.config.registry import (
    ModulePermissionDefine,
    PermNode,
    permission_registry,
)

LIFE_DEFINE = ModulePermissionDefine(
    module="life",
    name="生活工具",
    icon="Sunny",
    order_num=26,
    description="生活工具: 宝宝取名(生辰参考推算 + AI 起名)",
    nodes=[
        PermNode(
            name="宝宝取名",
            code="life:baby_name",
            menu_type="C",
            path="/life/baby_name",
            order_num=1,
            children=[
                PermNode(name="查询", code="life:baby_name:read", menu_type="F"),
                PermNode(name="起名", code="life:baby_name:generate", menu_type="F"),
                PermNode(name="新增", code="life:baby_name:create", menu_type="F"),
                PermNode(name="修改", code="life:baby_name:update", menu_type="F"),
                PermNode(name="删除", code="life:baby_name:delete", menu_type="F"),
            ],
        ),
    ],
    # 默认新模块不带权限(default_policies=[]):
    # 普通用户需管理员在 角色管理→分配权限 中按需勾选本模块权限码
    default_policies=[],
)

# 注册到权限中心(app 导入本模块 config 时生效)
permission_registry.register(LIFE_DEFINE)
