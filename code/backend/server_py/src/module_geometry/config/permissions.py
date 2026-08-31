"""
module_geometry 权限声明(地理空间模块自治声明本模块涉及的权限)

接入权限体系的步骤:
    1. 声明 ModulePermissionDefine(权限树 + 新用户默认权限)
    2. 底部调用 permission_registry.register() 完成注册
    3. 确保本文件被导入(由 app.py 导入,或在模块 config/server.py 中导入)
    4. 控制器路由使用 require_permission("geometry", "feature", "create") 等校验

域(dom)说明:
    "geometry"  地理空间模块域,模块内资源互相隔离于其他模块

角色说明: 不声明预设角色,全局仅 admin/user 两个内置角色;
需要细分角色由管理员在界面自建并勾选本模块权限码。

修改本模块权限只需编辑本文件,重启后自动幂等同步 casbin 与权限表。
"""
from module_authorization.config.registry import (
    ModulePermissionDefine,
    PermNode,
    permission_registry,
)

GEOMETRY_DEFINE = ModulePermissionDefine(
    module="geometry",
    name="地理空间",
    icon="Location",
    order_num=25,
    description="Babylon 地球场景点线面绘制与 PostGIS 空间数据管理",
    nodes=[
        PermNode(
            name="要素管理",
            code="geometry:feature",
            menu_type="C",
            path="/_sys/geometry/earth",
            order_num=1,
            children=[
                PermNode(name="查询", code="geometry:feature:read", menu_type="F"),
                PermNode(name="绘制", code="geometry:feature:create", menu_type="F"),
                PermNode(name="修改", code="geometry:feature:update", menu_type="F"),
                PermNode(name="删除", code="geometry:feature:delete", menu_type="F"),
            ],
        ),
    ],
    # 新注册用户默认权限: 可浏览与绘制
    default_policies=[
        ("geometry", "feature", "read"),
        ("geometry", "feature", "create"),
    ],
)

# 注册到权限中心(app 导入本模块 config 时生效)
permission_registry.register(GEOMETRY_DEFINE)
