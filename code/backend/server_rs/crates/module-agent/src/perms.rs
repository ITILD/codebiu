//! agent 域权限声明(对齐 Python module_agent/config/permissions.py)
//!
//! 归属规则: 自定义智能体为用户私有(仅创建者与管理员可改删), 不走 casbin 项目域;
//! 内置公共智能体全员可用。新用户默认权限: 可对话、可查看/创建/改删自己的简单智能体。

use module_authorization::perms::{ModulePermissionDefine, PermNode};

/// 智能体对话菜单(查看历史/发起对话)
pub const CHAT_NODE: PermNode = PermNode {
    name: "智能体对话",
    code: "agent:chat",
    menu_type: "C",
    description: None,
    path: Some("/agent/chat"),
    icon: None,
    order_num: 1,
    visible: true,
    children: &[
        PermNode { name: "查看历史", code: "agent:chat:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "发起对话", code: "agent:chat:write", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    ],
};

/// 智能体管理菜单(查看/创建/修改/删除)
pub const MANAGE_NODE: PermNode = PermNode {
    name: "智能体管理",
    code: "agent:manage",
    menu_type: "C",
    description: None,
    path: Some("/agent/manage"),
    icon: None,
    order_num: 2,
    visible: true,
    children: &[
        PermNode { name: "查看", code: "agent:manage:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "创建", code: "agent:manage:create", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "修改", code: "agent:manage:update", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "删除", code: "agent:manage:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    ],
};

/// agent 域声明(内置公共智能体与自定义简单智能体)
pub static AGENT_DEFINE: ModulePermissionDefine = ModulePermissionDefine {
    module: "agent",
    name: "智能体",
    icon: Some("MagicStick"),
    order_num: 11,
    description: Some("内置公共智能体与自定义简单智能体"),
    nodes: &[CHAT_NODE, MANAGE_NODE],
    default_policies: &[
        ("agent", "chat", "read"),
        ("agent", "chat", "write"),
        ("agent", "manage", "read"),
        ("agent", "manage", "create"),
        ("agent", "manage", "update"),
        ("agent", "manage", "delete"),
    ],
};

/// 注册 agent 域声明(启动期调用一次)
pub fn register_agent_define() {
    module_authorization::perms::register(&AGENT_DEFINE);
}
