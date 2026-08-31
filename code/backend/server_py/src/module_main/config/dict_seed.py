"""
字典种子注册中心(模块自治声明字典种子)

设计思路(与权限注册中心 registry.py 同构):
    module_main 在此声明系统通用基础字典(sys 域),
    各业务模块(rag/blog/...)在自己模块的 config/dict_seed.py 中声明本模块域字典,
    启动时由 DictBootstrapService(见 module_main/service/bootstrap.py)统一批量幂等同步到
    dict_type/dict_item 两张表(只补缺,不更新不删除,管理员的界面修改不会被覆盖)。

新增业务模块接入步骤:
    1. 在模块下新建 config/dict_seed.py, 声明 DictTypeSeed 并注册
    2. 在模块 config/server.py(或被 app.py 导入的任意入口)导入该文件完成注册
"""
from dataclasses import dataclass, field


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
