//! 字典种子声明(对齐 Python module_main/config/dict_seed.py 的注册中心内容)
//!
//! module_main 声明系统通用基础字典(sys 域); 后续业务模块在各自模块中声明本模块域字典,
//! 启动时由 bootstrap::ensure_default_dicts 统一批量幂等同步(只补缺,不覆盖)。

/// 字典项种子声明
pub struct DictItemSeed {
    /// 字典项编码(存储值,与代码枚举对齐)
    pub item_code: &'static str,
    /// 字典项显示名
    pub item_name: &'static str,
    /// 附加值(如 true/false)
    pub item_value: Option<&'static str>,
    /// 描述
    pub description: Option<&'static str>,
    /// 排序顺序(0 = 按声明顺序)
    pub sort_order: i32,
}

/// 字典类型种子声明(一个字典类型及其全部字典项)
pub struct DictTypeSeed {
    /// 字典类型编码(全局唯一,建议加模块前缀)
    pub type_code: &'static str,
    /// 字典类型名称
    pub type_name: &'static str,
    /// 描述
    pub description: Option<&'static str>,
    /// 排序顺序(0 = 按注册顺序)
    pub sort_order: i32,
    /// 字典项种子列表
    pub items: &'static [DictItemSeed],
}

const fn item(code: &'static str, name: &'static str, value: Option<&'static str>) -> DictItemSeed {
    DictItemSeed { item_code: code, item_name: name, item_value: value, description: None, sort_order: 0 }
}

/// 全部字典类型种子(声明顺序即同步顺序)
pub static SEEDS: &[DictTypeSeed] = &[
    // 通用状态(各表 is_active 字段的状态显示)
    DictTypeSeed {
        type_code: "sys_common_status",
        type_name: "通用状态",
        description: Some("各表 is_active 字段的状态显示字典"),
        sort_order: 1,
        items: &[item("enabled", "启用", Some("true")), item("disabled", "停用", Some("false"))],
    },
    // 是否(布尔值显示)
    DictTypeSeed {
        type_code: "sys_yes_no",
        type_name: "是否",
        description: Some("布尔值的显示字典"),
        sort_order: 2,
        items: &[item("yes", "是", Some("true")), item("no", "否", Some("false"))],
    },
    // 性别
    DictTypeSeed {
        type_code: "sys_gender",
        type_name: "性别",
        description: Some("用户性别显示字典"),
        sort_order: 3,
        items: &[
            item("male", "男", None),
            item("female", "女", None),
            item("unknown", "未知", None),
        ],
    },
];
