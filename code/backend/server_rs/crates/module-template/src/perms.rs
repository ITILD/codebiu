//! template 域权限声明
//!
//! 说明: Python module_template 侧没有 config/permissions.py(无权限声明),
//! 此处按系统权限码约定("模块:资源:动作")补齐声明, 供启动期注册与角色管理勾选;
//! default_policies 为空: 普通用户需管理员在角色管理中按需勾选本模块权限码。

use module_authorization::perms::{ModulePermissionDefine, PermNode};

/// 模板管理菜单(查询/创建/更新/删除)
pub const TEMPLATE_NODE: PermNode = PermNode {
    name: "模板管理",
    code: "template:template",
    menu_type: "C",
    description: None,
    path: Some("/template/templates"),
    icon: None,
    order_num: 1,
    visible: true,
    children: &[
        PermNode { name: "查询", code: "template:template:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "创建", code: "template:template:create", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "更新", code: "template:template:update", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "删除", code: "template:template:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    ],
};

/// 扩展模板菜单(上传/流式/WebSocket 示例)
pub const TEMPLATE_EX_NODE: PermNode = PermNode {
    name: "扩展模板",
    code: "template:template_ex",
    menu_type: "C",
    description: None,
    path: Some("/template/template-ex"),
    icon: None,
    order_num: 2,
    visible: true,
    children: &[
        PermNode { name: "查询", code: "template:template_ex:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "上传", code: "template:template_ex:create", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    ],
};

/// 异步示例菜单(四种执行模式演示)
pub const ASYNC_LEARN_NODE: PermNode = PermNode {
    name: "异步示例",
    code: "template:async_learn",
    menu_type: "C",
    description: None,
    path: Some("/template/template-async-learn"),
    icon: None,
    order_num: 3,
    visible: true,
    children: &[
        PermNode { name: "查询", code: "template:async_learn:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    ],
};

/// template 域声明(默认新模块不带权限)
pub static TEMPLATE_DEFINE: ModulePermissionDefine = ModulePermissionDefine {
    module: "template",
    name: "基础模板",
    icon: None,
    order_num: 26,
    description: Some("基础模板: 模板CRUD/扩展示例/异步并发示例"),
    nodes: &[TEMPLATE_NODE, TEMPLATE_EX_NODE, ASYNC_LEARN_NODE],
    default_policies: &[],
};

/// 注册 template 域声明(启动期调用一次)
pub fn register_template_define() {
    module_authorization::perms::register(&TEMPLATE_DEFINE);
}
