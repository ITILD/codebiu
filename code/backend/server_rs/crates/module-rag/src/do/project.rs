//! 项目/成员/部门授权 DTO(对齐 Python module_rag/do/project.py、
//! project_member.py、project_dept.py)

use sea_orm::prelude::DateTimeWithTimeZone;
use serde::{Deserialize, Serialize};

/// 知识库分类合法值(personal/project/company)
pub const KB_CATEGORIES: [&str; 3] = ["personal", "project", "company"];

/// 项目成员可分配的角色集合(固定三档, GitHub 式)
pub const PROJECT_ROLES: [&str; 3] = ["project_admin", "project_editor", "project_reader"];

/// 角色档位等级(数值越大权限越高; 未知角色 0)
pub fn role_level(role: &str) -> i32 {
    match role {
        "project_reader" => 1,
        "project_editor" => 2,
        "project_admin" => 3,
        _ => 0,
    }
}

/// project_editor 档位值(下载授权判定用)
pub const EDITOR_LEVEL: i32 = 2;

// ==================== 项目 ====================

/// 创建项目请求(仅 name/description/is_private/kb_category)
#[derive(Debug, Deserialize)]
pub struct ProjectCreate {
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default = "d_true")]
    pub is_private: bool,
    #[serde(default = "d_project_category")]
    pub kb_category: String,
}

fn d_true() -> bool {
    true
}

fn d_project_category() -> String {
    "project".to_string()
}

/// 更新项目请求(None=不更新)
#[derive(Debug, Default, Deserialize)]
pub struct ProjectUpdate {
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub is_private: Option<bool>,
    #[serde(default)]
    pub kb_category: Option<String>,
}

/// 当前用户对单个知识库的操作权限位(前端按位渲染按钮)
#[derive(Debug, Clone, Serialize)]
pub struct ProjectMyPerms {
    pub read: bool,
    pub upload_doc: bool,
    pub update: bool,
    pub download: bool,
    pub delete: bool,
    pub manage_member: bool,
}

impl ProjectMyPerms {
    /// 权限位全 True(全局管理员)
    pub fn full() -> Self {
        Self { read: true, upload_doc: true, update: true, download: true, delete: true, manage_member: true }
    }

    /// 按生效档位映射权限位(upload_doc/update/download ≥2, delete/manage_member ≥3)
    pub fn from_level(level: i32) -> Self {
        Self {
            read: level >= 1,
            upload_doc: level >= 2,
            update: level >= 2,
            download: level >= 2,
            delete: level >= 3,
            manage_member: level >= 3,
        }
    }
}

/// 项目响应(列表/详情返回, 含当前用户权限位)
#[derive(Debug, Serialize)]
pub struct ProjectResponse {
    pub id: String,
    pub name: String,
    pub description: Option<String>,
    pub is_private: bool,
    pub kb_category: String,
    pub created_by: String,
    pub root_entry_id: Option<String>,
    pub created_at: Option<DateTimeWithTimeZone>,
    pub updated_at: DateTimeWithTimeZone,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub my_perms: Option<ProjectMyPerms>,
}

// ==================== 项目成员 ====================

/// 创建项目成员请求
#[derive(Debug, Deserialize)]
pub struct ProjectMemberCreate {
    pub user_id: String,
    pub project_id: String,
    pub role: String,
}

/// 更新项目成员请求(None=不更新)
#[derive(Debug, Default, Deserialize)]
pub struct ProjectMemberUpdate {
    #[serde(default)]
    pub role: Option<String>,
}

/// 项目成员响应
#[derive(Debug, Serialize)]
pub struct ProjectMemberResponse {
    pub id: String,
    pub user_id: String,
    pub project_id: String,
    pub role: String,
    pub created_at: Option<DateTimeWithTimeZone>,
    pub updated_at: DateTimeWithTimeZone,
}

/// 成员列表项(联 user 表输出账号/昵称, 对齐 Python controller 的联查口径)
#[derive(Debug, Serialize)]
pub struct ProjectMemberWithUser {
    #[serde(flatten)]
    pub member: ProjectMemberResponse,
    /// 用户名(联查)
    pub username: Option<String>,
    /// 昵称(联查)
    pub nickname: Option<String>,
}

/// 我参与的项目响应
#[derive(Debug, Serialize)]
pub struct MyProjectResponse {
    pub project_id: String,
    pub project_name: String,
    pub project_description: Option<String>,
    pub is_private: bool,
    pub kb_category: String,
    pub role: String,
    pub created_at: Option<DateTimeWithTimeZone>,
}

// ==================== 部门授权 ====================

/// 创建部门授权请求
#[derive(Debug, Deserialize)]
pub struct ProjectDeptCreate {
    pub project_id: String,
    pub dept_id: String,
    pub role: String,
}

/// 更新部门授权请求(None=不更新)
#[derive(Debug, Default, Deserialize)]
pub struct ProjectDeptUpdate {
    #[serde(default)]
    pub role: Option<String>,
}

/// 部门授权响应
#[derive(Debug, Serialize)]
pub struct ProjectDeptResponse {
    pub id: String,
    pub project_id: String,
    pub dept_id: String,
    pub role: String,
    pub created_at: Option<DateTimeWithTimeZone>,
    pub updated_at: DateTimeWithTimeZone,
}

/// 部门授权列表项(联 dept 表输出部门名, 便于前端展示)
#[derive(Debug, Serialize)]
pub struct ProjectDeptWithDept {
    #[serde(flatten)]
    pub dept_auth: ProjectDeptResponse,
    /// 部门名称(联查)
    pub dept_name: Option<String>,
}

/// 角色合法性校验(非法 → 400 文案与 Python 一致)
pub fn validate_role(role: &str) -> Result<(), String> {
    if PROJECT_ROLES.contains(&role) {
        Ok(())
    } else {
        Err(format!(
            "无效的角色 '{role}'，允许的角色: {}",
            PROJECT_ROLES.join("/")
        ))
    }
}

/// 知识库分类合法性校验(非法 → 400 文案与 Python 一致)
pub fn validate_kb_category(category: &str) -> Result<(), String> {
    if KB_CATEGORIES.contains(&category) {
        Ok(())
    } else {
        Err(format!(
            "无效的知识库分类 '{category}'，允许的值: {}",
            KB_CATEGORIES.join("/")
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn 角色档位单调递增() {
        assert_eq!(role_level("project_reader"), 1);
        assert_eq!(role_level("project_editor"), 2);
        assert_eq!(role_level("project_admin"), 3);
        // 未知角色 0 档(无权限)
        assert_eq!(role_level("hacker"), 0);
        assert_eq!(EDITOR_LEVEL, 2);
    }

    #[test]
    fn 角色与分类校验文案() {
        assert!(validate_role("project_admin").is_ok());
        let err = validate_role("owner").unwrap_err();
        assert!(err.contains("无效的角色"));
        assert!(validate_kb_category("company").is_ok());
        assert!(validate_kb_category("team").is_err());
    }
}
