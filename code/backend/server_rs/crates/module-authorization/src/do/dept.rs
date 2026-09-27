//! 部门 DTO(对齐 Python do/dept.py: DeptCreate/DeptUpdate/DeptResponse/DeptTree)

use chrono::{DateTime, FixedOffset};
use serde::{Deserialize, Serialize};

use crate::do_::default_parent_id;

/// 部门创建请求
#[derive(Debug, Clone, Deserialize)]
pub struct DeptCreate {
    #[serde(default = "default_parent_id")]
    pub parent_id: String,
    pub name: String,
    #[serde(default)]
    pub order_num: Option<i32>,
    #[serde(default)]
    pub leader: Option<String>,
    #[serde(default)]
    pub phone: Option<String>,
    #[serde(default)]
    pub email: Option<String>,
    #[serde(default)]
    pub is_active: Option<bool>,
}

/// 部门更新请求(全部可选; 传 parent_id 时服务端自动重算 ancestors)
#[derive(Debug, Clone, Deserialize, Default)]
pub struct DeptUpdate {
    #[serde(default)]
    pub parent_id: Option<String>,
    #[serde(default)]
    pub ancestors: Option<String>,
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub order_num: Option<i32>,
    #[serde(default)]
    pub leader: Option<String>,
    #[serde(default)]
    pub phone: Option<String>,
    #[serde(default)]
    pub email: Option<String>,
    #[serde(default)]
    pub is_active: Option<bool>,
}

/// 部门详情响应(对齐 Python DeptResponse: 基础字段 + id/时间戳)
#[derive(Debug, Clone, Serialize)]
pub struct DeptResponse {
    pub parent_id: Option<String>,
    pub ancestors: String,
    pub name: String,
    pub order_num: i32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub leader: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub phone: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub email: Option<String>,
    pub is_active: bool,
    pub id: String,
    pub created_at: DateTime<FixedOffset>,
    pub updated_at: DateTime<FixedOffset>,
}

impl From<crate::do_::entity::dept::Model> for DeptResponse {
    fn from(d: crate::do_::entity::dept::Model) -> Self {
        use crate::do_::now_utc;
        Self {
            id: d.id,
            parent_id: d.parent_id,
            ancestors: d.ancestors,
            name: d.name,
            order_num: d.order_num,
            leader: d.leader,
            phone: d.phone,
            email: d.email,
            is_active: d.is_active,
            created_at: d.created_at.unwrap_or_else(now_utc),
            updated_at: d.updated_at,
        }
    }
}

/// 部门树节点(响应, 对齐 Python DeptTree: 不含 ancestors)
#[derive(Debug, Clone, Serialize)]
pub struct DeptTreeNode {
    pub id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub parent_id: Option<String>,
    pub name: String,
    pub order_num: i32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub leader: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub phone: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub email: Option<String>,
    pub is_active: bool,
    pub children: Vec<DeptTreeNode>,
}
