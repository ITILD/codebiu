//! 字典项数据对象(对齐 Python module_main/do/dict_item.py)

use serde::Deserialize;

/// 创建字典项(对齐 DictItemCreate)
#[derive(Debug, Deserialize)]
pub struct DictItemCreate {
    /// 字典类型ID
    pub dict_type_id: String,
    /// 字典项编码
    pub item_code: String,
    /// 字典项名称
    pub item_name: String,
    /// 字典项值
    #[serde(default)]
    pub item_value: Option<String>,
    /// 字典项描述
    #[serde(default)]
    pub description: Option<String>,
    /// 是否激活状态
    #[serde(default = "crate::do_::d_true")]
    pub is_active: bool,
    /// 排序顺序
    #[serde(default)]
    pub sort_order: i32,
}

/// 更新字典项(对齐 DictItemUpdate; 仅显式传入的字段生效)
#[derive(Debug, Deserialize)]
pub struct DictItemUpdate {
    pub dict_type_id: String,
    pub item_code: String,
    pub item_name: String,
    #[serde(default)]
    pub item_value: Option<Option<String>>,
    #[serde(default)]
    pub description: Option<Option<String>>,
    #[serde(default)]
    pub is_active: Option<bool>,
    #[serde(default)]
    pub sort_order: Option<i32>,
}
