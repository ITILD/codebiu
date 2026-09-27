//! geometry 域权限声明(对齐 Python module_geometry/config/permissions.py 的 GEOMETRY_DEFINE)
//!
//! 地理空间模块: Babylon 地球场景点线面绘制与空间数据管理。
//! default_policies 为空: 普通用户需管理员在角色管理中按需勾选本模块权限码。

use module_authorization::perms::{ModulePermissionDefine, PermNode};

/// 要素管理菜单(查询/绘制/修改/删除)
pub const FEATURE_NODE: PermNode = PermNode {
    name: "要素管理",
    code: "geometry:feature",
    menu_type: "C",
    description: None,
    path: Some("/geometry/earth"),
    icon: None,
    order_num: 1,
    visible: true,
    children: &[
        PermNode { name: "查询", code: "geometry:feature:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "绘制", code: "geometry:feature:create", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "修改", code: "geometry:feature:update", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "删除", code: "geometry:feature:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    ],
};

/// geometry 域声明(新用户默认不带权限, 对齐 Python default_policies=[])
pub static GEOMETRY_DEFINE: ModulePermissionDefine = ModulePermissionDefine {
    module: "geometry",
    name: "地理空间",
    icon: Some("Location"),
    order_num: 25,
    description: Some("Babylon 地球场景点线面绘制与 PostGIS 空间数据管理"),
    nodes: &[FEATURE_NODE],
    default_policies: &[],
};

/// 注册 geometry 域声明(启动期调用一次)
pub fn register_geometry_define() {
    module_authorization::perms::register(&GEOMETRY_DEFINE);
}
