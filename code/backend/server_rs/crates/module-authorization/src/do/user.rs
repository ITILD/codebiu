//! 用户 DTO(对齐 Python do/user.py: UserResponse/UserCreate/UserUpdate)

use chrono::{DateTime, FixedOffset};
use serde::{Deserialize, Serialize};

use crate::do_::entity::user;

use crate::do_::now_utc;

/// 用户响应(不含密码, 对齐 Python UserResponse)
#[derive(Debug, Clone, Serialize)]
pub struct UserResponse {
    pub id: String,
    pub username: String,
    pub dept_id: Option<String>,
    pub email: Option<String>,
    pub phone: Option<String>,
    pub nickname: Option<String>,
    pub avatar: Option<String>,
    pub is_active: bool,
    pub created_at: DateTime<FixedOffset>,
    pub updated_at: DateTime<FixedOffset>,
}

impl From<user::Model> for UserResponse {
    fn from(u: user::Model) -> Self {
        Self {
            id: u.id,
            username: u.username,
            dept_id: u.dept_id,
            email: u.email,
            phone: u.phone,
            nickname: u.nickname,
            avatar: u.avatar,
            is_active: u.is_active,
            created_at: u.created_at.unwrap_or_else(now_utc),
            updated_at: u.updated_at,
        }
    }
}

/// 用户创建请求
#[derive(Debug, Clone, Deserialize)]
pub struct UserCreate {
    pub username: String,
    pub password: String,
    #[serde(default)]
    pub dept_id: Option<String>,
    #[serde(default)]
    pub email: Option<String>,
    #[serde(default)]
    pub phone: Option<String>,
    #[serde(default)]
    pub nickname: Option<String>,
    #[serde(default)]
    pub avatar: Option<String>,
    #[serde(default)]
    pub is_active: Option<bool>,
}

/// 用户更新请求(全部可选, 仅更新传入字段)
#[derive(Debug, Clone, Deserialize, Default)]
pub struct UserUpdate {
    #[serde(default)]
    pub username: Option<String>,
    #[serde(default)]
    pub password: Option<String>,
    #[serde(default)]
    pub dept_id: Option<String>,
    #[serde(default)]
    pub email: Option<String>,
    #[serde(default)]
    pub phone: Option<String>,
    #[serde(default)]
    pub nickname: Option<String>,
    #[serde(default)]
    pub avatar: Option<String>,
    #[serde(default)]
    pub is_active: Option<bool>,
}

impl UserUpdate {
    /// 是否包含任意待更新字段
    pub fn has_any(&self) -> bool {
        self.username.is_some()
            || self.password.is_some()
            || self.dept_id.is_some()
            || self.email.is_some()
            || self.phone.is_some()
            || self.nickname.is_some()
            || self.avatar.is_some()
            || self.is_active.is_some()
    }
}
