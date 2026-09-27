//! 系统管理域(sys)权限声明(对齐 Python module_permissions.py 的 SYS_DEFINE)
//!
//! 授权模块自身管理资源: 用户/角色/部门/权限/策略规则(各含增删改查按钮)

use crate::perms::{self, ModulePermissionDefine, PermNode};

// code 含模块名拼接, const fn 无法构造格式化字符串, 故五个节点直接手写声明(与 Python 输出逐字段一致)

/// 用户管理菜单(查询/新增/修改/删除)
pub const USER_NODE: PermNode = PermNode {
    name: "用户管理",
    code: "sys:user",
    menu_type: "C",
    description: None,
    path: Some("/authorization/user"),
    icon: Some("UserFilled"),
    order_num: 1,
    visible: true,
    children: &[
        PermNode { name: "查询", code: "sys:user:read", menu_type: "F", description: None, path: None, icon: None, order_num: 1, visible: true, children: &[] },
        PermNode { name: "新增", code: "sys:user:create", menu_type: "F", description: None, path: None, icon: None, order_num: 2, visible: true, children: &[] },
        PermNode { name: "修改", code: "sys:user:update", menu_type: "F", description: None, path: None, icon: None, order_num: 3, visible: true, children: &[] },
        PermNode { name: "删除", code: "sys:user:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 4, visible: true, children: &[] },
    ],
};

/// 角色管理菜单
pub const ROLE_NODE: PermNode = PermNode {
    name: "角色管理",
    code: "sys:role",
    menu_type: "C",
    description: None,
    path: Some("/authorization/role"),
    icon: Some("Avatar"),
    order_num: 2,
    visible: true,
    children: &[
        PermNode { name: "查询", code: "sys:role:read", menu_type: "F", description: None, path: None, icon: None, order_num: 1, visible: true, children: &[] },
        PermNode { name: "新增", code: "sys:role:create", menu_type: "F", description: None, path: None, icon: None, order_num: 2, visible: true, children: &[] },
        PermNode { name: "修改", code: "sys:role:update", menu_type: "F", description: None, path: None, icon: None, order_num: 3, visible: true, children: &[] },
        PermNode { name: "删除", code: "sys:role:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 4, visible: true, children: &[] },
    ],
};

/// 部门管理菜单
pub const DEPT_NODE: PermNode = PermNode {
    name: "部门管理",
    code: "sys:dept",
    menu_type: "C",
    description: None,
    path: Some("/authorization/dept"),
    icon: Some("OfficeBuilding"),
    order_num: 3,
    visible: true,
    children: &[
        PermNode { name: "查询", code: "sys:dept:read", menu_type: "F", description: None, path: None, icon: None, order_num: 1, visible: true, children: &[] },
        PermNode { name: "新增", code: "sys:dept:create", menu_type: "F", description: None, path: None, icon: None, order_num: 2, visible: true, children: &[] },
        PermNode { name: "修改", code: "sys:dept:update", menu_type: "F", description: None, path: None, icon: None, order_num: 3, visible: true, children: &[] },
        PermNode { name: "删除", code: "sys:dept:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 4, visible: true, children: &[] },
    ],
};

/// 权限配置菜单
pub const PERMISSION_NODE: PermNode = PermNode {
    name: "权限配置",
    code: "sys:permission",
    menu_type: "C",
    description: None,
    path: Some("/authorization/permission"),
    icon: Some("Key"),
    order_num: 4,
    visible: true,
    children: &[
        PermNode { name: "查询", code: "sys:permission:read", menu_type: "F", description: None, path: None, icon: None, order_num: 1, visible: true, children: &[] },
        PermNode { name: "新增", code: "sys:permission:create", menu_type: "F", description: None, path: None, icon: None, order_num: 2, visible: true, children: &[] },
        PermNode { name: "修改", code: "sys:permission:update", menu_type: "F", description: None, path: None, icon: None, order_num: 3, visible: true, children: &[] },
        PermNode { name: "删除", code: "sys:permission:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 4, visible: true, children: &[] },
    ],
};

/// 策略规则菜单
pub const CASBIN_NODE: PermNode = PermNode {
    name: "策略规则",
    code: "sys:casbin",
    menu_type: "C",
    description: None,
    path: Some("/authorization/casbin"),
    icon: Some("List"),
    order_num: 5,
    visible: true,
    children: &[
        PermNode { name: "查询", code: "sys:casbin:read", menu_type: "F", description: None, path: None, icon: None, order_num: 1, visible: true, children: &[] },
        PermNode { name: "新增", code: "sys:casbin:create", menu_type: "F", description: None, path: None, icon: None, order_num: 2, visible: true, children: &[] },
        PermNode { name: "修改", code: "sys:casbin:update", menu_type: "F", description: None, path: None, icon: None, order_num: 3, visible: true, children: &[] },
        PermNode { name: "删除", code: "sys:casbin:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 4, visible: true, children: &[] },
    ],
};

/// sys 域声明(新用户不自动获得系统管理权限, default_policies 为空)
pub static SYS_DEFINE: ModulePermissionDefine = ModulePermissionDefine {
    module: "sys",
    name: "系统管理",
    icon: Some("Monitor"),
    order_num: 1,
    description: Some("用户/角色/部门/权限/策略规则等系统基础管理"),
    nodes: &[USER_NODE, ROLE_NODE, DEPT_NODE, PERMISSION_NODE, CASBIN_NODE],
    default_policies: &[],
};

/// 注册 sys 域声明(启动期调用一次)
pub fn register_sys_define() {
    perms::register(&SYS_DEFINE);
}
