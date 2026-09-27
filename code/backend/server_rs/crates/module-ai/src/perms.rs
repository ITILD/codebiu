//! ai 域权限声明(对齐 Python module_authorization/config/module_permissions.py 的 AI_DEFINE)
//!
//! 模型配置管理菜单(查询/新增/修改/删除), 新用户默认持有只读权限。

use module_authorization::perms::{ModulePermissionDefine, PermNode};

/// 模型配置管理菜单(查询/新增/修改/删除)
pub const MODEL_CONFIG_NODE: PermNode = PermNode {
    name: "模型配置",
    code: "ai:model-config",
    menu_type: "C",
    description: None,
    path: Some("/ai/model-config"),
    icon: Some("MagicStick"),
    order_num: 1,
    visible: true,
    children: &[
        PermNode { name: "查询", code: "ai:model-config:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "新增", code: "ai:model-config:create", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "修改", code: "ai:model-config:update", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "删除", code: "ai:model-config:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    ],
};

/// ai 域声明(新用户默认拥有模型配置只读权限)
pub static AI_DEFINE: ModulePermissionDefine = ModulePermissionDefine {
    module: "ai",
    name: "AI能力",
    icon: Some("MagicStick"),
    order_num: 3,
    description: Some("模型配置/对话/OCR/重排序等 AI 能力"),
    nodes: &[MODEL_CONFIG_NODE],
    default_policies: &[("ai", "model-config", "read")],
};

/// 注册 ai 域声明(启动期调用一次)
pub fn register_ai_define() {
    module_authorization::perms::register(&AI_DEFINE);
}
