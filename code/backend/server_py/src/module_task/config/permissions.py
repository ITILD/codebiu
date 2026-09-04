"""
module_task 权限声明(任务队列模块自治声明本模块涉及的权限)

接入权限体系的步骤:
    1. 声明 ModulePermissionDefine(权限树 + 新用户默认权限)
    2. 底部调用 permission_registry.register() 完成注册
    3. 确保本文件被导入(由 app.py / 模块 config/server.py 导入)
    4. 控制器路由使用 require_permission("task", "queue", "create") 等校验

域(dom)说明:
    "task"  任务队列模块域,模块内资源互相隔离于其他模块

修改本模块权限只需编辑本文件,重启后自动幂等同步 casbin 与权限表。
"""
from module_authorization.config.registry import (
    ModulePermissionDefine,
    PermNode,
    permission_registry,
)

TASK_DEFINE = ModulePermissionDefine(
    module="task",
    name="任务队列",
    icon="Timer",
    order_num=30,
    description="Celery+Redis 异步任务队列: 创建任务/状态进度轮询/取消重试",
    nodes=[
        PermNode(
            name="任务管理",
            code="task:queue",
            menu_type="C",
            path="/task/queue",
            order_num=1,
            children=[
                PermNode(name="查询", code="task:queue:read", menu_type="F"),
                PermNode(name="创建", code="task:queue:create", menu_type="F"),
                PermNode(name="操作", code="task:queue:update", menu_type="F"),
                PermNode(name="删除", code="task:queue:delete", menu_type="F"),
            ],
        ),
    ],
    # 默认新模块不带权限(default_policies=[]):
    # 普通用户需管理员在 角色管理→分配权限 中按需勾选本模块权限码
    default_policies=[],
)

# 注册到权限中心(app 导入本模块 config 时生效)
permission_registry.register(TASK_DEFINE)
