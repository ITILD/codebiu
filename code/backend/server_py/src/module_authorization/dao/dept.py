from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update
from common.config.db import DaoRel
from module_authorization.do.dept import Dept, DeptCreate, DeptUpdate, DeptResponse


class DeptDao:
    @DaoRel
    async def add(
        self, dept: DeptCreate, session: AsyncSession | None = None
    ) -> DeptResponse:
        """新增部门记录"""
        db_dept = Dept.model_validate(dept.model_dump(exclude_unset=True))
        # 如果有父部门，查询父部门的ancestors并构建当前部门的ancestors
        if dept.parent_id and dept.parent_id != "0":
            parent = await session.get(Dept, dept.parent_id)
            if parent:
                db_dept.ancestors = f"{parent.ancestors},{parent.id}" if parent.ancestors else parent.id
            else:
                db_dept.ancestors = "0"
        else:
            db_dept.ancestors = "0"
        session.add(db_dept)
        await session.flush()
        return DeptResponse.model_validate(db_dept.model_dump())

    @DaoRel
    async def delete(self, id: str, session: AsyncSession | None = None):
        """删除部门记录"""
        dept = await session.get(Dept, id)
        if not dept:
            raise ValueError(f"未找到ID为 {id} 的部门")
        await session.delete(dept)
        await session.flush()

    @DaoRel
    async def update(
        self,
        dept_id: str,
        dept: DeptUpdate,
        session: AsyncSession | None = None,
    ):
        """更新部门记录"""
        update_data = dept.model_dump(exclude_unset=True)
        # 如果修改了parent_id，需要重新计算ancestors
        if "parent_id" in update_data and update_data["parent_id"]:
            new_parent_id = update_data["parent_id"]
            if new_parent_id != "0":
                parent = await session.get(Dept, new_parent_id)
                if parent:
                    update_data["ancestors"] = f"{parent.ancestors},{parent.id}" if parent.ancestors else parent.id
                else:
                    update_data["ancestors"] = "0"
            else:
                update_data["ancestors"] = "0"
        stmt = update(Dept).where(Dept.id == dept_id).values(**update_data)
        result = await session.exec(stmt)
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {dept_id} 的部门")
        await session.flush()

    @DaoRel
    async def get(self, id: str, session: AsyncSession | None = None) -> DeptResponse:
        """查询单个部门"""
        dept = await session.get(Dept, id)
        if not dept:
            raise ValueError(f"未找到ID为 {id} 的部门")
        return DeptResponse.model_validate(dept.model_dump())

    @DaoRel
    async def get_raw(self, id: str, session: AsyncSession | None = None) -> Dept | None:
        """查询原始部门对象"""
        return await session.get(Dept, id)

    @DaoRel
    async def list_all(self, session: AsyncSession | None = None) -> list[Dept]:
        """查询所有部门(不分页, 用于构建树)"""
        statement = select(Dept).order_by(Dept.order_num)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def get_children(
        self, parent_id: str, session: AsyncSession | None = None
    ) -> list[Dept]:
        """查询子部门列表"""
        statement = select(Dept).where(Dept.parent_id == parent_id).order_by(Dept.order_num)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def has_children(
        self, dept_id: str, session: AsyncSession | None = None
    ) -> bool:
        """检查部门是否有子部门"""
        statement = select(func.count()).select_from(Dept).where(Dept.parent_id == dept_id)
        result = await session.exec(statement)
        return result.one() > 0

    @DaoRel
    async def get_by_name(
        self, name: str, session: AsyncSession | None = None
    ) -> Dept | None:
        """根据名称查询部门"""
        statement = select(Dept).where(Dept.name == name)
        result = await session.exec(statement)
        return result.first()
