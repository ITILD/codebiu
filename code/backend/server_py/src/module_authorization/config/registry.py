"""
权限注册中心(模块自治声明权限的核心)

设计思路:
    module_authorization 负责"基础权限"(用户/角色/权限的管理与鉴权基建),
    各业务模块(rag/blog/...)在自己模块的 config/permissions.py 中声明本模块涉及的
    权限树(菜单/按钮)与新用户默认权限,启动时通过注册中心幂等同步到:
        1. casbin 策略表(p: 角色-域-资源-动作)
        2. role 表(角色字典)
        3. permission 表(权限/菜单树,供前端权限管理与角色授权使用)

角色体系(简化为两级,若依/GitHub 式):
    内置角色仅两个:
        admin  全局管理员,权限穿透一切(策略 "admin" -> "*/*/*")
        user   普通用户,策略由各模块的 default_policies 声明合并而来
    其余角色由管理员在界面自建并勾选权限树的节点权限码
    项目级权限不走 casbin,由业务模块成员表固定档位判断(如 module_rag 的
    project_admin/project_editor/project_reader)

权限码(code)约定:
    "模块"           目录节点(M),如 "rag"
    "模块:资源"       菜单节点(C),如 "rag:project"
    "模块:资源:动作"  按钮节点(F),如 "rag:project:create"
    按钮节点可直接解析为 casbin 四元组 (sub=角色, dom=模块, obj=资源, act=动作)

新增业务模块接入步骤:
    1. 在模块下新建 config/permissions.py, 声明 ModulePermissionDefine
    2. 在模块 config/server.py(或被 app.py 导入的任意入口)导入该文件完成注册
    3. 控制器路由使用 require_permission(模块, 资源, 动作) 校验
"""
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class PermNode:
    """权限树节点声明(目录/菜单/按钮)"""

    name: str  # 节点显示名
    code: str  # 权限码: "模块" / "模块:资源" / "模块:资源:动作"
    menu_type: str = "C"  # 菜单类型: M=目录 C=菜单 F=按钮
    description: str | None = None  # 描述
    path: str | None = None  # 前端路由路径(菜单节点)
    icon: str | None = None  # 图标名
    order_num: int = 0  # 显示顺序
    visible: bool = True  # 是否可见
    children: list["PermNode"] = field(default_factory=list)

    def walk(self):
        """深度优先遍历自身与全部子孙节点"""
        yield self
        for child in self.children:
            yield from child.walk()


@dataclass
class ModulePermissionDefine:
    """模块权限声明(一个业务模块的完整权限定义)"""

    module: str  # 模块域名,同时是该模块权限树的根节点 code,如 "rag"/"blog"
    name: str  # 模块显示名,如 "知识库"
    icon: str | None = None  # 模块图标名
    order_num: int = 0  # 模块在权限树中的排序
    description: str | None = None
    nodes: list[PermNode] = field(default_factory=list)  # 模块权限树(不含模块根节点)
    # 新用户默认权限(并入内置 user 角色的 casbin 策略),每项为 (域, 资源, 动作)
    default_policies: list[tuple[str, str, str]] = field(default_factory=list)


def parse_perm_code(code: str) -> tuple[str, str, str] | None:
    """
    解析按钮级权限码为 casbin 四元组前三项
    :param code: 权限码,如 "rag:project:create"
    :return: (dom, obj, act) 元组;非按钮级权限码(段数!=3)返回 None
    """
    parts = code.split(":")
    if len(parts) != 3 or not all(parts):
        return None
    return parts[0], parts[1], parts[2]


class PermissionRegistry:
    """权限注册中心(单例),收集各模块的权限声明"""

    def __init__(self):
        self._defines: dict[str, ModulePermissionDefine] = {}

    def register(self, define: ModulePermissionDefine) -> None:
        """注册模块权限声明(模块 config 导入时调用,幂等:重复注册覆盖旧声明)"""
        if define.module in self._defines:
            logger.warning(f"模块 '{define.module}' 权限声明重复注册,以最新声明为准")
        self._defines[define.module] = define
        logger.info(f"模块权限声明已注册: {define.module}({define.name})")

    def get(self, module: str) -> ModulePermissionDefine | None:
        """获取指定模块的权限声明"""
        return self._defines.get(module)

    def get_all(self) -> list[ModulePermissionDefine]:
        """获取全部模块权限声明(按模块排序字段排序)"""
        return sorted(self._defines.values(), key=lambda d: d.order_num)

    def iter_node_policies(self) -> list[tuple[str, str, str]]:
        """
        遍历全部模块权限树,收集所有按钮级节点对应的 casbin 策略四元组前三项
        用于: 角色授权界面的"可分配权限集合" / 用户权限码展开
        """
        policies: list[tuple[str, str, str]] = []
        for define in self.get_all():
            for node in define.nodes:
                for leaf in node.walk():
                    parsed = parse_perm_code(leaf.code)
                    if parsed:
                        policies.append(parsed)
        return policies

    def default_user_policies(self) -> list[tuple[str, str, str]]:
        """
        收集全部模块声明的新用户默认权限(合并为内置 user 角色的 casbin 策略)
        :return: [(dom, obj, act), ...]
        """
        policies: list[tuple[str, str, str]] = []
        for define in self.get_all():
            policies.extend(define.default_policies)
        return policies


# 全局注册中心单例(各模块 config/permissions.py 导入并调用 register)
permission_registry = PermissionRegistry()
