//! dev_tools 域权限声明
//!
//! 说明: Python module_dev_tools 侧没有 config/permissions.py(无权限声明),
//! 此处按系统权限码约定补齐声明; default_policies 为空: 普通用户需管理员按需勾选。

use module_authorization::perms::{ModulePermissionDefine, PermNode};

/// 模板字符串菜单(查询/创建/更新/删除/渲染/语法校验)
pub const TEMPLATE_STRING_NODE: PermNode = PermNode {
    name: "模板字符串",
    code: "dev_tools:template_string",
    menu_type: "C",
    description: None,
    path: Some("/dev-tools/template-strings"),
    icon: None,
    order_num: 1,
    visible: true,
    children: &[
        PermNode { name: "查询", code: "dev_tools:template_string:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "创建", code: "dev_tools:template_string:create", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "更新", code: "dev_tools:template_string:update", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "删除", code: "dev_tools:template_string:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "渲染", code: "dev_tools:template_string:render", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "语法校验", code: "dev_tools:template_string:validate", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    ],
};

/// dev_tools 域声明(默认新模块不带权限)
pub static DEV_TOOLS_DEFINE: ModulePermissionDefine = ModulePermissionDefine {
    module: "dev_tools",
    name: "开发辅助",
    icon: None,
    order_num: 27,
    description: Some("开发辅助: string.Template 模板字符串管理与渲染"),
    nodes: &[TEMPLATE_STRING_NODE],
    default_policies: &[],
};

/// 注册 dev_tools 域声明(启动期调用一次)
pub fn register_dev_tools_define() {
    module_authorization::perms::register(&DEV_TOOLS_DEFINE);
}
