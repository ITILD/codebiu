//! 权限 DTO(对齐 Python do/permission.py: PermissionCreate/Update/Tree 与校验响应)

use serde::{Deserialize, Serialize};

/// 权限创建请求
#[derive(Debug, Clone, Deserialize)]
pub struct PermissionCreate {
    #[serde(default)]
    pub parent_id: Option<String>,
    pub name: String,
    pub code: String,
    #[serde(default)]
    pub description: Option<String>,
    /// M=目录 C=菜单 F=按钮
    pub menu_type: String,
    #[serde(default)]
    pub path: Option<String>,
    #[serde(default)]
    pub component: Option<String>,
    #[serde(default)]
    pub perms: Option<String>,
    #[serde(default)]
    pub icon: Option<String>,
    #[serde(default)]
    pub order_num: Option<i32>,
    #[serde(default)]
    pub visible: Option<bool>,
    #[serde(default)]
    pub is_active: Option<bool>,
}

/// 权限更新请求(全部可选)
#[derive(Debug, Clone, Deserialize, Default)]
pub struct PermissionUpdate {
    #[serde(default)]
    pub parent_id: Option<String>,
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub code: Option<String>,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub menu_type: Option<String>,
    #[serde(default)]
    pub path: Option<String>,
    #[serde(default)]
    pub component: Option<String>,
    #[serde(default)]
    pub perms: Option<String>,
    #[serde(default)]
    pub icon: Option<String>,
    #[serde(default)]
    pub order_num: Option<i32>,
    #[serde(default)]
    pub visible: Option<bool>,
    #[serde(default)]
    pub is_active: Option<bool>,
}

/// 权限树节点(响应, 字段对齐 Python PermissionTree)
#[derive(Debug, Clone, Serialize)]
pub struct PermissionTreeNode {
    pub id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub parent_id: Option<String>,
    pub name: String,
    pub code: String,
    pub menu_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub perms: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub icon: Option<String>,
    pub order_num: i32,
    pub visible: bool,
    pub is_active: bool,
    pub children: Vec<PermissionTreeNode>,
}

/// 权限校验结果(POST /casbin-rules/check-permission 响应)
#[derive(Debug, Clone, Serialize)]
pub struct PermissionCheckResponse {
    pub has_permission: bool,
}
