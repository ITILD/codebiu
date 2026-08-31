"""
module_blog 权限声明示例(博客模块自治声明本模块涉及的权限)

本文件演示新业务模块接入权限体系的完整步骤:
    1. 声明 ModulePermissionDefine(权限树 + 新用户默认权限)
    2. 底部调用 permission_registry.register() 完成注册
    3. 确保本文件被导入(由 app.py 导入,或在模块 config/server.py 中导入)
    4. 控制器路由使用 require_permission("blog", "post", "create") 等校验

域(dom)说明:
    "blog"  博客模块域,模块内资源互相隔离于其他模块

角色说明: 不声明预设角色,全局仅 admin/user 两个内置角色;
需要细分角色(如博客作者)由管理员在界面自建并勾选本模块权限码。

修改本模块权限只需编辑本文件,重启后自动幂等同步 casbin 与权限表。
"""
from module_authorization.config.registry import (
    ModulePermissionDefine,
    PermNode,
    permission_registry,
)

BLOG_DEFINE = ModulePermissionDefine(
    module="blog",
    name="博客",
    icon="EditPen",
    order_num=20,
    description="博客文章/分类/评论管理",
    nodes=[
        PermNode(
            name="文章管理",
            code="blog:post",
            menu_type="C",
            path="/_sys/blog/post",
            order_num=1,
            children=[
                PermNode(name="查询", code="blog:post:read", menu_type="F"),
                PermNode(name="发布", code="blog:post:create", menu_type="F"),
                PermNode(name="修改", code="blog:post:update", menu_type="F"),
                PermNode(name="删除", code="blog:post:delete", menu_type="F"),
            ],
        ),
        PermNode(
            name="分类管理",
            code="blog:category",
            menu_type="C",
            path="/_sys/blog/category",
            order_num=2,
            children=[
                PermNode(name="查询", code="blog:category:read", menu_type="F"),
                PermNode(name="新增", code="blog:category:create", menu_type="F"),
                PermNode(name="修改", code="blog:category:update", menu_type="F"),
                PermNode(name="删除", code="blog:category:delete", menu_type="F"),
            ],
        ),
        PermNode(
            name="评论管理",
            code="blog:comment",
            menu_type="C",
            path="/_sys/blog/comment",
            order_num=3,
            children=[
                PermNode(name="查询", code="blog:comment:read", menu_type="F"),
                PermNode(name="发表", code="blog:comment:create", menu_type="F"),
                PermNode(name="审核", code="blog:comment:audit", menu_type="F"),
                PermNode(name="删除", code="blog:comment:delete", menu_type="F"),
            ],
        ),
    ],
    # 新注册用户默认权限: 仅浏览与评论
    default_policies=[
        ("blog", "post", "read"),
        ("blog", "category", "read"),
        ("blog", "comment", "read"),
        ("blog", "comment", "create"),
    ],
)

# 注册到权限中心(app 导入本模块 config 时生效)
permission_registry.register(BLOG_DEFINE)
