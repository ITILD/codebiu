"""
字典种子注册中心与启动引导(模块自治声明字典种子)

设计思路(与权限注册中心 registry.py 同构):
    module_main 在此声明系统通用基础字典(sys 域),
    各业务模块(rag/blog/...)在自己模块的 config/dict_seed.py 中声明本模块域字典,
    启动时由本文件的 ensure_default_dicts 统一批量幂等同步到
    dict_type/dict_item 两张表(只补缺,不更新不删除,管理员的界面修改不会被覆盖)。

新增业务模块接入步骤:
    1. 在模块下新建 config/dict_seed.py, 声明 DictTypeSeed 并注册
    2. 在模块 config/server.py(或被 app.py 导入的任意入口)导入该文件完成注册
"""
from dataclasses import dataclass, field

from sqlmodel import select

from common.config.db import db_rel
from module_main.do.dict_type import DictType
from module_main.do.dict_item import DictItem
import logging

logger = logging.getLogger(__name__)


@dataclass
class DictItemSeed:
    """字典项种子声明"""

    item_code: str  # 字典项编码(存储值,与代码枚举对齐)
    item_name: str  # 字典项显示名
    item_value: str | None = None  # 附加值(如 true/false)
    description: str | None = None  # 描述
    sort_order: int = 0  # 排序顺序(默认按声明顺序)


@dataclass
class DictTypeSeed:
    """字典类型种子声明(一个字典类型及其全部字典项)"""

    type_code: str  # 字典类型编码(全局唯一,建议加模块前缀)
    type_name: str  # 字典类型名称
    description: str | None = None  # 描述
    sort_order: int = 0  # 排序顺序(默认按注册顺序)
    items: list[DictItemSeed] = field(default_factory=list)  # 字典项种子列表


class DictSeedRegistry:
    """字典种子注册中心"""

    def __init__(self):
        self._seeds: dict[str, DictTypeSeed] = {}

    def register(self, seed: DictTypeSeed) -> None:
        """
        注册字典类型种子(按 type_code 覆盖式注册)
        :param seed: 字典类型种子
        """
        self._seeds[seed.type_code] = seed

    def get_all(self) -> list[DictTypeSeed]:
        """获取全部已注册的字典类型种子(按注册顺序)"""
        return list(self._seeds.values())


# 全局注册中心单例
dict_seed_registry = DictSeedRegistry()

# ---------------- 系统通用基础字典(sys 域) ----------------

# 注册: 通用状态(各表 is_active 字段的状态显示)
dict_seed_registry.register(
    DictTypeSeed(
        type_code="sys_common_status",
        type_name="通用状态",
        description="各表 is_active 字段的状态显示字典",
        sort_order=1,
        items=[
            DictItemSeed(item_code="enabled", item_name="启用", item_value="true"),
            DictItemSeed(item_code="disabled", item_name="停用", item_value="false"),
        ],
    )
)

# 注册: 是否(布尔值显示)
dict_seed_registry.register(
    DictTypeSeed(
        type_code="sys_yes_no",
        type_name="是否",
        description="布尔值的显示字典",
        sort_order=2,
        items=[
            DictItemSeed(item_code="yes", item_name="是", item_value="true"),
            DictItemSeed(item_code="no", item_name="否", item_value="false"),
        ],
    )
)

# 注册: 性别
dict_seed_registry.register(
    DictTypeSeed(
        type_code="sys_gender",
        type_name="性别",
        description="用户性别显示字典",
        sort_order=3,
        items=[
            DictItemSeed(item_code="male", item_name="男"),
            DictItemSeed(item_code="female", item_name="女"),
            DictItemSeed(item_code="unknown", item_name="未知"),
        ],
    )
)


# ---------------- 启动引导(批量幂等同步) ----------------

async def ensure_default_dicts() -> None:
    """
    将注册中心的字典种子声明幂等同步到 dict_type/dict_item 表(建表后启动钩子调用)
    :raises Exception: 数据库操作异常时向上抛出(由调用方决定是否阻断启动)
    """
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
