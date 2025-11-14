from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from module_authorization.do.casbin_rule import CasbinRule
from common.config.db import DaoRel


class CasbinRuleDao:
    """Casbin规则数据访问对象"""

    @DaoRel
    async def create(self, casbin_rule: CasbinRule, session: AsyncSession | None = None) -> CasbinRule:
        """创建Casbin规则

        Args:
            casbin_rule: Casbin规则对象
            session: 可选数据库会话

        Returns:
            创建后的Casbin规则对象
        """
        session.add(casbin_rule)
        await session.flush()
        return casbin_rule

    @DaoRel
    async def batch_create(self, casbin_rules: list[CasbinRule], session: AsyncSession | None = None) -> list[CasbinRule]:
        """批量创建Casbin规则

        Args:
            casbin_rules: Casbin规则对象列表
            session: 可选数据库会话

        Returns:
            创建后的Casbin规则对象列表
        """
        session.add_all(casbin_rules)
        await session.flush()
        return casbin_rules

    @DaoRel
    async def get_by_id(self, id: int, session: AsyncSession | None = None) -> CasbinRule | None:
        """根据ID获取Casbin规则

        Args:
            id: 规则ID
            session: 可选数据库会话

        Returns:
            Casbin规则对象，如果不存在则返回None
        """
        return await session.get(CasbinRule, id)

    @DaoRel
    async def get_all(self, session: AsyncSession | None = None) -> list[CasbinRule]:
        """获取所有Casbin规则

        Args:
            session: 可选数据库会话

        Returns:
            Casbin规则对象列表
        """
        statement = select(CasbinRule)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def delete_by_id(self, id: int, session: AsyncSession | None = None) -> bool:
        """根据ID删除Casbin规则

        Args:
            id: 规则ID
            session: 可选数据库会话

        Returns:
            删除是否成功
        """
        rule = await self.get_by_id(id, session)
        if rule:
            await session.delete(rule)
            await session.flush()
            return True
        return False

    @DaoRel
    async def delete_batch(self, ids: list[int], session: AsyncSession | None = None) -> int:
        """批量删除Casbin规则

        Args:
            ids: 规则ID列表
            session: 可选数据库会话

        Returns:
            删除的规则数量
        """
        statement = select(CasbinRule).where(CasbinRule.id.in_(ids))
        rules = (await session.exec(statement)).all()
        for rule in rules:
            await session.delete(rule)
        await session.flush()
        return len(rules)

    @DaoRel
    async def delete_by_sub_obj_act(self, sub: str, obj: str, act: str, session: AsyncSession | None = None) -> int:
        """根据主体、对象和动作删除Casbin规则

        Args:
            sub: 主体
            obj: 对象
            act: 动作
            session: 可选数据库会话

        Returns:
            删除的规则数量
        """
        statement = select(CasbinRule).where(
            CasbinRule.v0 == sub,
            CasbinRule.v1 == obj,
            CasbinRule.v2 == act,
            CasbinRule.ptype == "p"
        )
        rules = (await session.exec(statement)).all()
        for rule in rules:
            await session.delete(rule)
        await session.flush()
        return len(rules)

    @DaoRel
    async def delete_by_role_permission(self, role_key: str, permission_code: str, method: str, session: AsyncSession | None = None) -> int:
        """根据角色和权限删除Casbin规则

        Args:
            role_key: 角色键
            permission_code: 权限代码
            method: 请求方法
            session: 可选数据库会话

        Returns:
            删除的规则数量
        """
        return await self.delete_by_sub_obj_act(role_key, permission_code, method, session)


    @DaoRel
    async def get_role_permissions(self, role_key: str, session: AsyncSession | None = None) -> list[tuple]:
        """获取角色的所有权限

        Args:
            role_key: 角色键
            session: 可选数据库会话

        Returns:
            权限列表，每项为(permission_code, method)元组
        """
        statement = select(CasbinRule.v1, CasbinRule.v2).where(
            CasbinRule.v0 == role_key,
            CasbinRule.ptype == "p"
        )
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def delete_role_permissions(self, role_key: str, session: AsyncSession | None = None) -> int:
        """删除角色的所有权限

        Args:
            role_key: 角色键
            session: 可选数据库会话

        Returns:
            删除的权限数量
        """
        statement = select(CasbinRule).where(
            CasbinRule.v0 == role_key,
            CasbinRule.ptype == "p"
        )
        rules = (await session.exec(statement)).all()
        for rule in rules:
            await session.delete(rule)
        await session.flush()
        return len(rules)

    @DaoRel
    async def delete_user_roles(self, user_id: str, session: AsyncSession | None = None) -> int:
        """删除用户的所有角色

        Args:
            user_id: 用户ID
            session: 可选数据库会话

        Returns:
            删除的角色数量
        """
        statement = select(CasbinRule).where(
            CasbinRule.v0 == user_id,
            CasbinRule.ptype == "g"
        )
        rules = (await session.exec(statement)).all()
        for rule in rules:
            await session.delete(rule)
        await session.flush()
        return len(rules)