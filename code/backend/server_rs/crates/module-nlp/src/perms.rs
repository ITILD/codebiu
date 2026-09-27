//! nlp 域权限声明
//!
//! 说明: Python module_nlp 侧没有 config/permissions.py(无权限声明),
//! 此处按系统权限码约定补齐声明; default_policies 为空: 普通用户需管理员按需勾选。

use module_authorization::perms::{ModulePermissionDefine, PermNode};

/// 同义词组菜单(查询/创建/更新/删除)
pub const SYNONYM_GROUP_NODE: PermNode = PermNode {
    name: "同义词组",
    code: "nlp:synonym_group",
    menu_type: "C",
    description: None,
    path: Some("/nlp/synonyms/groups"),
    icon: None,
    order_num: 1,
    visible: true,
    children: &[
        PermNode { name: "查询", code: "nlp:synonym_group:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "创建", code: "nlp:synonym_group:create", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "更新", code: "nlp:synonym_group:update", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "删除", code: "nlp:synonym_group:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    ],
};

/// 同义词菜单(查询/批量创建/批量更新/删除)
pub const SYNONYM_NODE: PermNode = PermNode {
    name: "同义词",
    code: "nlp:synonym",
    menu_type: "C",
    description: None,
    path: Some("/nlp/synonyms"),
    icon: None,
    order_num: 2,
    visible: true,
    children: &[
        PermNode { name: "查询", code: "nlp:synonym:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "创建", code: "nlp:synonym:create", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "更新", code: "nlp:synonym:update", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "删除", code: "nlp:synonym:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    ],
};

/// nlp 域声明(默认新模块不带权限)
pub static NLP_DEFINE: ModulePermissionDefine = ModulePermissionDefine {
    module: "nlp",
    name: "同义词",
    icon: None,
    order_num: 28,
    description: Some("同义词管理: 同义词组与词语维护/搜索/聚合"),
    nodes: &[SYNONYM_GROUP_NODE, SYNONYM_NODE],
    default_policies: &[],
};

/// 注册 nlp 域声明(启动期调用一次)
pub fn register_nlp_define() {
    module_authorization::perms::register(&NLP_DEFINE);
}
