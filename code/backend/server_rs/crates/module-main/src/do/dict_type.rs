//! 字典类型数据对象(对齐 Python module_main/do/dict_type.py)

use serde::Deserialize;

/// 创建字典类型(对齐 DictTypeCreate)
#[derive(Debug, Deserialize)]
pub struct DictTypeCreate {
    /// 字典类型编码
    pub type_code: String,
    /// 字典类型名称
    pub type_name: String,
    /// 字典类型描述
    #[serde(default)]
    pub description: Option<String>,
    /// 是否激活状态
    #[serde(default = "crate::do_::d_true")]
    pub is_active: bool,
    /// 排序顺序
    #[serde(default)]
    pub sort_order: i32,
}

/// 更新字典类型(对齐 DictTypeUpdate; 仅显式传入的字段生效)
#[derive(Debug, Deserialize)]
pub struct DictTypeUpdate {
    pub type_code: String,
    pub type_name: String,
    #[serde(default)]
    pub description: Option<Option<String>>,
    #[serde(default)]
    pub is_active: Option<bool>,
    #[serde(default)]
    pub sort_order: Option<i32>,
}
