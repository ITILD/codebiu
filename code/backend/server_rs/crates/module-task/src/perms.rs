//! task 域权限声明(对齐 Python module_task/config/permissions.py 的 TASK_DEFINE)
//!
//! 域(dom)说明: "task" 任务队列模块域, 模块内资源互相隔离于其他模块。
//! 默认新模块不带权限(default_policies=[]): 普通用户需管理员在 角色管理→分配权限 中按需勾选。

use module_authorization::perms::{ModulePermissionDefine, PermNode};

/// 任务管理菜单(查询/创建/操作/删除)
pub const QUEUE_NODE: PermNode = PermNode {
    name: "任务管理",
    code: "task:queue",
    menu_type: "C",
    description: None,
    path: Some("/task/queue"),
    icon: None,
    order_num: 1,
    visible: true,
    children: &[
        PermNode { name: "查询", code: "task:queue:read", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "创建", code: "task:queue:create", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "操作", code: "task:queue:update", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
        PermNode { name: "删除", code: "task:queue:delete", menu_type: "F", description: None, path: None, icon: None, order_num: 0, visible: true, children: &[] },
    ],
};

/// task 域声明(权限树 + 新用户默认权限)
pub static TASK_DEFINE: ModulePermissionDefine = ModulePermissionDefine {
    module: "task",
    name: "任务队列",
    icon: Some("Timer"),
    order_num: 30,
    description: Some("Celery+Redis 异步任务队列: 创建任务/状态进度轮询/取消重试"),
    nodes: &[QUEUE_NODE],
    default_policies: &[],
};

/// 注册 task 域声明(启动期调用一次, 幂等: 重复注册按模块名覆盖)
pub fn register_task_define() {
    module_authorization::perms::register(&TASK_DEFINE);
}
