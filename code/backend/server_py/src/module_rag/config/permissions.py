"""
module_rag 权限声明(知识库模块自治声明本模块涉及的权限)

域(dom)说明:
    "rag"  知识库模块全局域(项目列表/创建项目/对话等模块级资源)

角色说明: 本模块不声明预设角色;项目内权限由 project_member 表的固定档位
(project_admin/project_editor/project_reader)控制,详见
module_rag/dependencies/permission.py,不走 casbin 项目域。

修改本模块权限只需编辑本文件,重启后自动幂等同步 casbin 与权限表。
"""
from module_authorization.config.registry import (
    ModulePermissionDefine,
    PermNode,
    permission_registry,
)

RAG_DEFINE = ModulePermissionDefine(
    module="rag",
    name="知识库",
    icon="Collection",
    order_num=10,
    description="知识库项目/文档/成员/对话管理",
    nodes=[
        PermNode(
            name="项目管理",
            code="rag:project",
            menu_type="C",
            path="/_sys/rag/project",
            order_num=1,
            children=[
                PermNode(name="查询", code="rag:project:read", menu_type="F"),
                PermNode(name="创建", code="rag:project:create", menu_type="F"),
                PermNode(name="修改", code="rag:project:update", menu_type="F"),
                PermNode(name="删除", code="rag:project:delete", menu_type="F"),
            ],
        ),
        PermNode(
            name="文档管理",
            code="rag:doc",
            menu_type="C",
            path="/_sys/rag/document",
            order_num=2,
            children=[
                PermNode(name="查看/下载", code="rag:doc:read", menu_type="F"),
                PermNode(name="上传", code="rag:doc:upload", menu_type="F"),
                PermNode(name="修改", code="rag:doc:update", menu_type="F"),
                PermNode(name="删除", code="rag:doc:delete", menu_type="F"),
            ],
        ),
        PermNode(
            name="成员管理",
            code="rag:member",
            menu_type="C",
            path="/_sys/rag/member",
            order_num=3,
            children=[
                PermNode(name="查看", code="rag:member:read", menu_type="F"),
                PermNode(name="邀请", code="rag:member:invite", menu_type="F"),
                PermNode(name="变更角色", code="rag:member:update", menu_type="F"),
                PermNode(name="移除", code="rag:member:remove", menu_type="F"),
            ],
        ),
        PermNode(
            name="知识库问答",
            code="rag:chat",
            menu_type="C",
            path="/_sys/rag/conversation",
            order_num=4,
            children=[
                PermNode(name="查看历史", code="rag:chat:read", menu_type="F"),
                PermNode(name="发起问答", code="rag:chat:write", menu_type="F"),
            ],
        ),
    ],
    # 新注册用户默认权限: 可浏览项目列表、创建个人知识库并对话
    # (项目内资源的访问由成员表档位控制)
    default_policies=[
        ("rag", "project", "read"),
        ("rag", "project", "create"),
        ("rag", "chat", "read"),
        ("rag", "chat", "write"),
    ],
)

# 注册到权限中心(app 导入本模块 config 时生效)
permission_registry.register(RAG_DEFINE)
