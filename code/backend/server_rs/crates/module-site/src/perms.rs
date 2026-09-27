//! site 域权限声明(对齐 Python module_site/config/permissions.py 的 SITE_DEFINE)
//!
//! 三条业务线: blog 博客 / memo 备忘 / ledger 记账。
//! 按钮节点未声明 order_num(与 Python 一致, 默认 0);
//! default_policies 为空: 普通用户需管理员在角色管理中按需勾选本模块权限码。

use module_authorization::perms::{ModulePermissionDefine, PermNode};

/// 博客菜单(发布/修改/删除/查询)
pub const BLOG_NODE: PermNode = PermNode {
    name: "博客",
    code: "site:blog",
    menu_type: "C",
    description: None,
    path: Some("/site/blog"),
    icon: None,
    order_num: 1,
    visible: true,
    children: &[
        PermNode { name: "查询", code: "site:blog:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "发布", code: "site:blog:create", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "修改", code: "site:blog:update", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "删除", code: "site:blog:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    ],
};

/// 备忘菜单(承接原 todolist 业务, 权限码保持 memo)
pub const MEMO_NODE: PermNode = PermNode {
    name: "备忘",
    code: "site:memo",
    menu_type: "C",
    description: None,
    path: Some("/site/memo"),
    icon: None,
    order_num: 2,
    visible: true,
    children: &[
        PermNode { name: "查询", code: "site:memo:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "新增", code: "site:memo:create", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "修改", code: "site:memo:update", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "删除", code: "site:memo:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    ],
};

/// 记账菜单
pub const LEDGER_NODE: PermNode = PermNode {
    name: "记账",
    code: "site:ledger",
    menu_type: "C",
    description: None,
    path: Some("/site/ledger"),
    icon: None,
    order_num: 3,
    visible: true,
    children: &[
        PermNode { name: "查询", code: "site:ledger:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "新增", code: "site:ledger:create", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "修改", code: "site:ledger:update", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "删除", code: "site:ledger:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    ],
};

/// site 域声明(默认新模块不带权限)
pub static SITE_DEFINE: ModulePermissionDefine = ModulePermissionDefine {
    module: "site",
    name: "个人小站",
    icon: Some("Notebook"),
    order_num: 25,
    description: Some("个人小站: 博客发布/备忘管理/记账本"),
    nodes: &[BLOG_NODE, MEMO_NODE, LEDGER_NODE],
    default_policies: &[],
};

/// 注册 site 域声明(启动期调用一次)
pub fn register_site_define() {
    module_authorization::perms::register(&SITE_DEFINE);
}
