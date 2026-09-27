//! main 域权限声明(对齐 Python module_authorization/config/module_permissions.py 的 MAIN_DEFINE)
//!
//! 系统基础资源: 字典/数据库/虚拟文件系统/网页搜索等。
//! 按钮节点未声明 order_num(与 Python 一致, 默认 0)。

use module_authorization::perms::{ModulePermissionDefine, PermNode};

/// 字典管理菜单(查询/新增/修改/删除)
pub const DICT_NODE: PermNode = PermNode {
    name: "字典管理",
    code: "main:dict",
    menu_type: "C",
    description: None,
    path: Some("/main/dict"),
    icon: Some("Notebook"),
    order_num: 1,
    visible: true,
    children: &[
        PermNode { name: "查询", code: "main:dict:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "新增", code: "main:dict:create", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "修改", code: "main:dict:update", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "删除", code: "main:dict:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    ],
};

/// 数据库管理菜单(仅查询)
pub const DB_NODE: PermNode = PermNode {
    name: "数据库管理",
    code: "main:db",
    menu_type: "C",
    description: None,
    path: Some("/main/overview"),
    icon: Some("Coin"),
    order_num: 2,
    visible: true,
    children: &[
        PermNode { name: "查询", code: "main:db:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    ],
};

/// 文件管理菜单(下载为独立权限: 默认仅 admin 持有)
pub const FILE_NODE: PermNode = PermNode {
    name: "文件管理",
    code: "main:file",
    menu_type: "C",
    description: None,
    path: Some("/file"),
    icon: Some("FolderOpened"),
    order_num: 3,
    visible: true,
    children: &[
        PermNode { name: "浏览", code: "main:file:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "下载", code: "main:file:download", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "上传/新建", code: "main:file:create", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "重命名/移动", code: "main:file:update", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "删除", code: "main:file:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "存储迁移", code: "main:file:migrate", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    ],
};

/// 网页搜索菜单
pub const SEARCH_NODE: PermNode = PermNode {
    name: "网页搜索",
    code: "main:search",
    menu_type: "C",
    description: None,
    path: None,
    icon: Some("Search"),
    order_num: 4,
    visible: true,
    children: &[
        PermNode { name: "使用", code: "main:search:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    ],
};

/// 通用配置菜单(管理员专属, 不进 default_policies)
pub const CONFIG_NODE: PermNode = PermNode {
    name: "通用配置",
    code: "main:config",
    menu_type: "C",
    description: None,
    path: Some("/main/config"),
    icon: Some("Setting"),
    order_num: 5,
    visible: true,
    children: &[
        PermNode { name: "查看", code: "main:config:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "修改", code: "main:config:update", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    ],
};

/// main 域声明(新用户默认拥有各资源只读权限, 通用配置除外)
pub static MAIN_DEFINE: ModulePermissionDefine = ModulePermissionDefine {
    module: "main",
    name: "基础资源",
    icon: Some("Files"),
    order_num: 2,
    description: Some("字典/数据库/虚拟文件系统/网页搜索等系统基础资源"),
    nodes: &[DICT_NODE, DB_NODE, FILE_NODE, SEARCH_NODE, CONFIG_NODE],
    default_policies: &[
        ("main", "dict", "read"),
        ("main", "db", "read"),
        ("main", "file", "read"),
        ("main", "search", "read"),
    ],
};

/// 注册 main 域声明(启动期调用一次)
pub fn register_main_define() {
    module_authorization::perms::register(&MAIN_DEFINE);
}
