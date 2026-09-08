"""
module_agent 权限声明(智能体模块自治声明本模块涉及的权限)

域(dom)说明:
    "agent"  智能体模块全局域(对话/管理)

归属规则: 自定义智能体为用户私有(仅创建者与管理员可改删),
不走 casbin 项目域; 内置公共智能体全员可用。
"""
from module_authorization.config.registry import (
    ModulePermissionDefine,
    PermNode,
    permission_registry,
)

AGENT_DEFINE = ModulePermissionDefine(
    module="agent",
    name="智能体",
    icon="MagicStick",
    order_num=11,
    description="内置公共智能体与自定义简单智能体",
    nodes=[
        PermNode(
            name="智能体对话",
            code="agent:chat",
            menu_type="C",
            path="/agent/chat",
            order_num=1,
            children=[
                PermNode(name="查看历史", code="agent:chat:read", menu_type="F"),
                PermNode(name="发起对话", code="agent:chat:write", menu_type="F"),
            ],
        ),
        PermNode(
            name="智能体管理",
            code="agent:manage",
            menu_type="C",
            path="/agent/manage",
            order_num=2,
            children=[
                PermNode(name="查看", code="agent:manage:read", menu_type="F"),
                PermNode(name="创建", code="agent:manage:create", menu_type="F"),
                PermNode(name="修改", code="agent:manage:update", menu_type="F"),
                PermNode(name="删除", code="agent:manage:delete", menu_type="F"),
            ],
        ),
    ],
    # 新注册用户默认权限: 可对话、可查看/创建/改删自己的简单智能体
    default_policies=[
        ("agent", "chat", "read"),
        ("agent", "chat", "write"),
        ("agent", "manage", "read"),
        ("agent", "manage", "create"),
        ("agent", "manage", "update"),
        ("agent", "manage", "delete"),
    ],
)

# 注册到权限中心(app 导入本模块 config 时生效)
permission_registry.register(AGENT_DEFINE)
