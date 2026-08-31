"""
字典种子引导服务(启动时幂等同步基础字典)

与 casbin 策略初始化同思路的批量查缺方案:
    1. 两次 SELECT 批量拉取现有字典类型与字典项
    2. 内存中与注册中心的种子声明做 diff
    3. 缺失部分 session.add_all 一次批量写入,整个流程单事务,只输出一条汇总日志

幂等策略: 只补缺,不更新不删除——管理员在界面对字典的修改不会被启动同步覆盖。
"""
from sqlmodel import select

from common.config.db import db_rel
from module_main.do.dict_type import DictType
from module_main.do.dict_item import DictItem
import logging

logger = logging.getLogger(__name__)


class DictBootstrapService:
    """基础字典引导服务"""

    async def ensure_default_dicts(self) -> None:
        """
        将注册中心的字典种子声明幂等同步到 dict_type/dict_item 表
        :raises Exception: 数据库操作异常时向上抛出(由调用方决定是否阻断启动)
        """
        # 延迟导入触发基础字典注册(模块级注册),业务模块种子已在其 server.py 导入链注册
        from module_main.config.dict_seed import dict_seed_registry

        seeds = dict_seed_registry.get_all()
        if not seeds:
            logger.info("无字典种子声明,跳过初始化")
            return

        type_codes = [s.type_code for s in seeds]
        async with db_rel.session_factory() as session:
            async with session.begin():
                # ===== 批量查缺: 两次 SELECT 拉取现有数据 =====
                # 1) 现有字典类型(type_code -> 记录)
                stmt = select(DictType).where(DictType.type_code.in_(type_codes))
                existing_types = {
                    t.type_code: t for t in (await session.exec(stmt)).all()
                }
                # 2) 现有字典项((type_id, item_code) 集合),仅查种子类型的
                existing_items: set[tuple[str, str]] = set()
                type_ids = [t.id for t in existing_types.values()]
                if type_ids:
                    stmt = select(DictItem).where(DictItem.dict_type_id.in_(type_ids))
                    existing_items = {
                        (i.dict_type_id, i.item_code)
                        for i in (await session.exec(stmt)).all()
                    }

                # ===== 内存 diff + 批量插入 =====
                new_records: list[DictType | DictItem] = []
                added_types = 0
                added_items = 0
                for type_order, seed in enumerate(seeds, start=1):
                    existing_type = existing_types.get(seed.type_code)
                    if existing_type is not None:
                        type_id = existing_type.id
                    else:
                        # 新类型(id 由模型 default_factory 即时生成,可供字典项引用)
                        new_type = DictType(
                            type_code=seed.type_code,
                            type_name=seed.type_name,
                            description=seed.description,
                            sort_order=seed.sort_order or type_order,
                        )
                        new_records.append(new_type)
                        added_types += 1
                        type_id = new_type.id
                    for item_order, item in enumerate(seed.items, start=1):
                        if (type_id, item.item_code) in existing_items:
                            continue
                        new_records.append(
                            DictItem(
                                dict_type_id=type_id,
                                item_code=item.item_code,
                                item_name=item.item_name,
                                item_value=item.item_value,
                                description=item.description,
                                sort_order=item.sort_order or item_order,
                            )
                        )
                        added_items += 1

                if new_records:
                    session.add_all(new_records)
                    logger.info(
                        f"字典种子同步完成: 新增类型 {added_types} 个, 字典项 {added_items} 条"
                    )
                else:
                    logger.info("基础字典完整,无需补写")
