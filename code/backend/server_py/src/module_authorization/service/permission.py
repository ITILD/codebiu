from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_authorization.do.permission import Permission, PermissionCreate, PermissionUpdate, PermissionResponse, PermissionTree
from module_authorization.dao.permission import PermissionDao


class PermissionService:
    """权限服务"""

    def __init__(self, permission_dao: PermissionDao):
        self.permission_dao = permission_dao or PermissionDao()

    async def add(self, permission: PermissionCreate):
        """创建权限"""
        return await self.permission_dao.add(permission)

    async def delete(self, permission_id: str):
        """删除权限"""
        await self.permission_dao.delete(permission_id)

    async def update(self, permission_id: str, permission: PermissionUpdate):
        """更新权限"""
        await self.permission_dao.update(permission_id, permission)

    async def get(self, permission_id: str) -> Permission | None:
        """获取权限详情"""
        return await self.permission_dao.get(permission_id)

    async def get_by_code(self, code: str) -> Permission | None:
        """根据权限代码获取权限"""
        return await self.permission_dao.get_by_code(code)

    async def list_all(self, pagination: PaginationParams) -> PaginationResponse:
        """分页获取权限列表"""
        items = await self.permission_dao.list_all(pagination)
        total = await self.permission_dao.count()
        return PaginationResponse.create(items, total, pagination)

    async def get_permissions_by_parent_id(self, parent_id: str) -> list[Permission]:
        """获取指定父权限下的所有子权限"""
        return await self.permission_dao.get_by_parent_id(parent_id)

    async def get_tree(self) -> list[PermissionTree]:
        """获取权限树形结构"""
        permissions = await self.permission_dao.list_all_no_page()
        return self._build_tree(permissions)

    def _build_tree(self, permissions: list[Permission]) -> list[PermissionTree]:
        """构建权限树"""
        perm_map: dict[str, PermissionTree] = {}
        for perm in permissions:
            perm_map[perm.id] = PermissionTree(
                id=perm.id,
                parent_id=perm.parent_id,
                name=perm.name,
                code=perm.code,
                menu_type=perm.menu_type,
                perms=perm.perms,
                icon=perm.icon,
                order_num=perm.order_num,
                visible=perm.visible,
                is_active=perm.is_active,
                children=[],
            )
        root_list: list[PermissionTree] = []
        for perm in permissions:
            tree_node = perm_map[perm.id]
            if not perm.parent_id or perm.parent_id == "0":
                root_list.append(tree_node)
            else:
                parent_node = perm_map.get(perm.parent_id)
                if parent_node:
                    parent_node.children.append(tree_node)
                else:
                    root_list.append(tree_node)
        root_list.sort(key=lambda x: x.order_num)
        for node in root_list:
            self._sort_tree(node)
        return root_list

    def _sort_tree(self, node: PermissionTree):
        """递归排序树节点"""
        node.children.sort(key=lambda x: x.order_num)
        for child in node.children:
            self._sort_tree(child)
