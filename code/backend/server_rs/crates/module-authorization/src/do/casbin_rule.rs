//! casbin 规则 DTO(对齐 Python do/casbin_rule.py: 策略/绑角/批量授权请求与通用响应)

use serde::{Deserialize, Serialize};

use crate::do_::default_parent_id;

/// {message, data} 通用响应
#[derive(Debug, Clone, Serialize)]
pub struct MessageData<T: Serialize> {
    pub message: String,
    pub data: T,
}

impl<T: Serialize> MessageData<T> {
    pub fn ok(data: T) -> Self {
        Self { message: "ok".to_string(), data }
    }
    pub fn with_message(message: &str, data: T) -> Self {
        Self { message: message.to_string(), data }
    }
}

/// 策略规则请求 {sub, dom, obj, act}
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct PolicyRule {
    pub sub: String,
    pub dom: String,
    pub obj: String,
    pub act: String,
}

/// 用户-角色绑定请求
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct RoleUserRequest {
    pub user_id: String,
    pub role_key: String,
    #[serde(default = "default_parent_id")]
    pub dom: String,
}

/// 权限检查请求
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct CheckPermissionRequest {
    pub user_id: String,
    pub dom: String,
    pub obj: String,
    pub act: String,
}

/// 角色批量授权单项
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct BatchPermissionItem {
    pub permission_code: String,
    pub method: String,
}

/// 角色批量授权请求
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct BatchRolePermissionsRequest {
    pub role_key: String,
    #[serde(default = "default_parent_id")]
    pub dom: String,
    pub permissions: Vec<BatchPermissionItem>,
}

/// 用户批量绑角请求
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct BatchUserRolesRequest {
    pub user_id: String,
    #[serde(default = "default_parent_id")]
    pub dom: String,
    pub role_keys: Vec<String>,
}

/// 角色权限码调整请求(POST /role-perms)
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct RolePermsRequest {
    pub role_key: String,
    pub codes: Vec<String>,
}

/// 角色权限码调整结果
#[derive(Debug, Clone, Serialize)]
pub struct RolePermsResult {
    pub removed: usize,
    pub added: usize,
}
