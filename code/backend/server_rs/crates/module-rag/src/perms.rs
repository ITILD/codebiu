//! module-rag 权限声明(对齐 Python module_rag/config/permissions.py)
//!
//! 域(dom)说明:
//! - "rag": 知识库模块全局域(项目列表/创建项目/对话等模块级资源)
//!
//! 角色说明: 本模块不声明预设角色; 项目内权限由 project_member 表的固定档位
//! (project_admin/project_editor/project_reader)控制(见 services/permission.rs),
//! 不走 casbin 项目域。

use module_authorization::perms::{ModulePermissionDefine, PermNode};

/// 项目管理菜单下的按钮级权限
static PROJECT_NODES: [PermNode; 4] = [
    PermNode { name: "查询", code: "rag:project:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    PermNode { name: "创建", code: "rag:project:create", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    PermNode { name: "修改", code: "rag:project:update", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    PermNode { name: "删除", code: "rag:project:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
];

/// 文档管理菜单下的按钮级权限(下载独立于查看: 项目内下载按成员档位判定)
static DOC_NODES: [PermNode; 5] = [
    PermNode { name: "查看", code: "rag:doc:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    PermNode { name: "下载", code: "rag:doc:download", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    PermNode { name: "上传", code: "rag:doc:upload", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    PermNode { name: "修改", code: "rag:doc:update", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    PermNode { name: "删除", code: "rag:doc:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
];

/// 成员管理菜单下的按钮级权限
static MEMBER_NODES: [PermNode; 4] = [
    PermNode { name: "查看", code: "rag:member:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    PermNode { name: "邀请", code: "rag:member:invite", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    PermNode { name: "变更角色", code: "rag:member:update", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    PermNode { name: "移除", code: "rag:member:remove", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
];

/// 知识库问答菜单下的按钮级权限
static CHAT_NODES: [PermNode; 2] = [
    PermNode { name: "查看历史", code: "rag:chat:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    PermNode { name: "发起问答", code: "rag:chat:write", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
];

/// 菜单级节点(与 Python RAG_DEFINE.nodes 一致)
static RAG_NODES: [PermNode; 4] = [
    PermNode {
        name: "项目管理",
        code: "rag:project",
        menu_type: "C",
        description: None,
        path: Some("/rag/project"),
        icon: None,
        order_num: 1,
        visible: true,
        children: &PROJECT_NODES,
    },
    PermNode {
        name: "文档管理",
        code: "rag:doc",
        menu_type: "C",
        description: None,
        path: Some("/rag/document"),
        icon: None,
        order_num: 2,
        visible: true,
        children: &DOC_NODES,
    },
    PermNode {
        name: "成员管理",
        code: "rag:member",
        menu_type: "C",
        description: None,
        path: Some("/rag/member"),
        icon: None,
        order_num: 3,
        visible: true,
        children: &MEMBER_NODES,
    },
    PermNode {
        name: "知识库问答",
        code: "rag:chat",
        menu_type: "C",
        description: None,
        path: Some("/rag/conversation"),
        icon: None,
        order_num: 4,
        visible: true,
        children: &CHAT_NODES,
    },
];

/// 知识库模块权限定义(注册到权限中心, 启动期幂等同步 casbin 与权限表)
pub static RAG_DEFINE: ModulePermissionDefine = ModulePermissionDefine {
    module: "rag",
    name: "知识库",
    icon: Some("Collection"),
    order_num: 10,
    description: Some("知识库项目/文档/成员/对话管理"),
    nodes: &RAG_NODES,
    // 新注册用户默认权限: 可浏览项目列表、创建个人知识库并对话
    // (项目内资源的访问由成员表档位控制)
    default_policies: &[
        ("rag", "project", "read"),
        ("rag", "project", "create"),
        ("rag", "chat", "read"),
        ("rag", "chat", "write"),
    ],
};
