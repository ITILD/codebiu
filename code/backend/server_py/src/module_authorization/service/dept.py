from module_authorization.do.dept import DeptCreate, DeptUpdate, DeptResponse, DeptTree, Dept
from module_authorization.dao.dept import DeptDao


class DeptService:
    """部门服务"""

    def __init__(self, dept_dao: DeptDao):
        self.dept_dao = dept_dao or DeptDao()

    async def add(self, dept: DeptCreate) -> DeptResponse:
        """创建部门"""
        # 检查父部门是否存在
        if dept.parent_id and dept.parent_id != "0":
            parent = await self.dept_dao.get_raw(dept.parent_id)
            if not parent:
                raise ValueError(f"父部门ID {dept.parent_id} 不存在")
        # 检查同级部门名称是否重复
        existing = await self.dept_dao.get_by_name(dept.name)
        if existing:
            raise ValueError(f"部门名称 '{dept.name}' 已存在")
        return await self.dept_dao.add(dept)

    async def delete(self, dept_id: str):
        """删除部门"""
        # 检查是否有子部门
        has_children = await self.dept_dao.has_children(dept_id)
        if has_children:
            raise ValueError("存在子部门，不允许删除")
        await self.dept_dao.delete(dept_id)

    async def update(self, dept_id: str, dept: DeptUpdate):
        """更新部门"""
        await self.dept_dao.update(dept_id, dept)

    async def get(self, dept_id: str) -> DeptResponse:
        """获取部门详情"""
        return await self.dept_dao.get(dept_id)

    async def list_all(self) -> list[Dept]:
        """获取所有部门列表"""
        return await self.dept_dao.list_all()

    async def get_tree(self) -> list[DeptTree]:
        """获取部门树形结构"""
        depts = await self.dept_dao.list_all()
        return self._build_tree(depts)

    def _build_tree(self, depts: list[Dept]) -> list[DeptTree]:
        """构建部门树"""
        dept_map: dict[str, DeptTree] = {}
        for dept in depts:
            dept_map[dept.id] = DeptTree(
                id=dept.id,
                parent_id=dept.parent_id,
                name=dept.name,
                order_num=dept.order_num,
                leader=dept.leader,
                phone=dept.phone,
                email=dept.email,
                is_active=dept.is_active,
                children=[],
            )
        root_list: list[DeptTree] = []
        for dept in depts:
            tree_node = dept_map[dept.id]
            if not dept.parent_id or dept.parent_id == "0":
                root_list.append(tree_node)
            else:
                parent_node = dept_map.get(dept.parent_id)
                if parent_node:
                    parent_node.children.append(tree_node)
                else:
                    root_list.append(tree_node)
        # 按order_num排序
        root_list.sort(key=lambda x: x.order_num)
        for node in root_list:
            self._sort_tree(node)
        return root_list

    def _sort_tree(self, node: DeptTree):
        """递归排序树节点"""
        node.children.sort(key=lambda x: x.order_num)
        for child in node.children:
            self._sort_tree(child)
