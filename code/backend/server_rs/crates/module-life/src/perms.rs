//! life 域权限声明(对齐 Python module_life/config/permissions.py 的 LIFE_DEFINE)
//!
//! 业务线: baby_name 宝宝取名(参考体系严格推算 + AI 流式起名)。
//! default_policies 为空: 普通用户需管理员在角色管理中按需勾选本模块权限码。

use module_authorization::perms::{ModulePermissionDefine, PermNode};

/// 宝宝取名菜单(查询/起名/新增/修改/删除)
pub const BABY_NAME_NODE: PermNode = PermNode {
    name: "宝宝取名",
    code: "life:baby_name",
    menu_type: "C",
    description: None,
    path: Some("/life/baby_name"),
    icon: None,
    order_num: 1,
    visible: true,
    children: &[
        PermNode { name: "查询", code: "life:baby_name:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "起名", code: "life:baby_name:generate", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "新增", code: "life:baby_name:create", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "修改", code: "life:baby_name:update", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "删除", code: "life:baby_name:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    ],
};

/// life 域声明(默认新模块不带权限)
pub static LIFE_DEFINE: ModulePermissionDefine = ModulePermissionDefine {
    module: "life",
    name: "生活工具",
    icon: Some("Sunny"),
    order_num: 26,
    description: Some("生活工具: 宝宝取名(生辰参考推算 + AI 起名)"),
    nodes: &[BABY_NAME_NODE],
    default_policies: &[],
};

/// 注册 life 域声明(启动期调用一次)
pub fn register_life_define() {
    module_authorization::perms::register(&LIFE_DEFINE);
}
