//! 角色 DTO(对齐 Python do/role.py: RoleCreate/RoleUpdate)

use serde::Deserialize;

/// 角色创建请求
#[derive(Debug, Clone, Deserialize)]
pub struct RoleCreate {
    pub name: String,
    pub role_key: String,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub sort: Option<i32>,
    #[serde(default)]
    pub data_scope: Option<String>,
    #[serde(default)]
    pub is_active: Option<bool>,
}

/// 角色更新请求(全部可选)
#[derive(Debug, Clone, Deserialize, Default)]
pub struct RoleUpdate {
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub role_key: Option<String>,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub sort: Option<i32>,
    #[serde(default)]
    pub data_scope: Option<String>,
    #[serde(default)]
    pub is_active: Option<bool>,
}
