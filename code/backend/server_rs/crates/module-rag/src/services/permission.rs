//! 项目级权限校验(对齐 Python module_rag/dependencies/permission.py)
//!
//! 设计(GitHub 式): 角色存 project_member.role(直连成员)与 project_dept.role(部门授权),
//! 固定三档数值越大权限越高; 全局管理员穿透; 公开项目允许任何登录用户只读。

use common::runtime::AppState;
use common::utils::error::AppError;

use crate::dao::project as dao;
use crate::do_::project::{role_level, EDITOR_LEVEL};

/// 各动作所需档位(未列出的动作按最高档 3 从严处理)
fn action_level(act: &str) -> i32 {
    match act {
        "read" => 1,
        "upload" | "update" | "write" | "download" => 2,
        // publish: 公开/私有切换仅 project_admin, 防止 editor 泄露私有库(v4 3.1)
        "publish" | "delete" | "invite" | "remove" | "manage" => 3,
        _ => 3,
    }
}

/// 获取用户所在部门及其全部祖级部门ID(部门授权级联继承; 祖级链去根占位"0" + 自身)
pub async fn get_user_dept_chain(db: &sea_orm::DatabaseConnection, user_id: &str) -> Result<Vec<String>, AppError> {
    use sea_orm::EntityTrait;
    use module_authorization::do_::entity::{dept, user};
    let Some(u) = user::Entity::find_by_id(user_id.to_owned()).one(db).await? else {
        return Ok(Vec::new());
    };
    let Some(dept_id) = u.dept_id else {
        return Ok(Vec::new());
    };
    let Some(d) = dept::Entity::find_by_id(dept_id).one(db).await? else {
        return Ok(Vec::new());
    };
    let mut chain: Vec<String> = d
        .ancestors
        .split(',')
        .map(str::trim)
        .filter(|s| !s.is_empty() && *s != "0")
        .map(str::to_string)
        .collect();
    chain.push(d.id);
    Ok(chain)
}

/// 用户的部门授权档位(部门链命中授权的最高档; 无命中 0)
pub async fn get_dept_role_level(
    db: &sea_orm::DatabaseConnection,
    user_id: &str,
    project_id: &str,
) -> Result<i32, AppError> {
    let chain = get_user_dept_chain(db, user_id).await?;
    if chain.is_empty() {
        return Ok(0);
    }
    let roles = dao::dept_list_roles_by_dept_ids(db, project_id, &chain).await?;
    Ok(roles.iter().map(|r| role_level(r)).max().unwrap_or(0))
}

/// 用户在项目中的生效档位 = max(直连成员档位, 部门授权档位)
pub async fn get_effective_level(
    db: &sea_orm::DatabaseConnection,
    user_id: &str,
    project_id: &str,
) -> Result<i32, AppError> {
    let member_level = dao::member_get_by_user_and_project(db, user_id, project_id)
        .await?
        .map(|m| role_level(&m.role))
        .unwrap_or(0);
    let dept_level = get_dept_role_level(db, user_id, project_id).await?;
    Ok(member_level.max(dept_level))
}

/// 项目级权限检查(不抛异常): 管理员穿透 → 档位达标 → 公开项目只读
pub async fn check_project_permission(
    db: &sea_orm::DatabaseConnection,
    user_id: &str,
    project_id: &str,
    obj: &str,
    act: &str,
) -> Result<bool, AppError> {
    let _ = obj;
    // 1. 全局管理员穿透(casbin 全局域 admin)
    if module_authorization::casbin_mgr::auth().is_global_admin(user_id).await {
        return Ok(true);
    }
    // 2. 生效档位达到动作所需档位
    let required = action_level(act);
    if get_effective_level(db, user_id, project_id).await? >= required {
        return Ok(true);
    }
    // 3. 公开项目允许任何登录用户只读
    if act == "read" {
        if let Some(p) = dao::project_get(db, project_id).await? {
            if !p.is_private {
                return Ok(true);
            }
        }
    }
    Ok(false)
}

/// 项目级权限检查(无权限抛异常)
///
/// - read + 私有库 + 完全非成员(档位0): 404 防存在性探测(v4 3.3)
/// - 其余无权限: 403(文案与 Python 一致)
pub async fn enforce_project_permission(
    state: &AppState,
    user_id: &str,
    project_id: &str,
    obj: &str,
    act: &str,
) -> Result<(), AppError> {
    if check_project_permission(&state.db, user_id, project_id, obj, act).await? {
        return Ok(());
    }
    if act == "read" && get_effective_level(&state.db, user_id, project_id).await? == 0 {
        let project = dao::project_get(&state.db, project_id).await?;
        // 私有库对完全无关用户隐藏存在性; 项目本身不存在时同样 404
        if project.is_none() || project.is_some_and(|p| p.is_private) {
            return Err(AppError::not_found(format!("项目不存在: {project_id}")));
        }
    }
    Err(AppError::forbidden(format!("无项目操作权限: {project_id}/{obj}/{act}")))
}

/// 文件管理页下载 rag 业务条目的授权判定(注册到 module-file 下载授权中心)
///
/// 口径: 条目位于某项目根文件夹(root_entry_id)子树内, 且用户在该项目的
/// 生效档位 >= project_editor 时放行(全局管理员由 casbin main:file:download 穿透)。
async fn check_entry_download_grant(state: AppState, user_id: String, entry_id: String) -> bool {
    let file_service = module_file::services::filesystem::FileService::new(state.clone(), false);
    // 沿 pid 向上收集祖先链(含自身), 命中 project.root_entry_id 即定位所属项目
    let mut chain: Vec<String> = vec![entry_id.clone()];
    let mut cursor_id = entry_id;
    for _ in 0..64 {
        let Ok(Some(entry)) = file_service.get_file_entry(&cursor_id).await else {
            break;
        };
        match entry.pid {
            Some(pid) => {
                chain.push(pid.clone());
                cursor_id = pid;
            }
            None => break,
        }
    }
    let Ok(projects) = dao::project_get_by_root_entry_ids(&state.db, &chain).await else {
        return false;
    };
    for project in projects {
        if get_effective_level(&state.db, &user_id, &project.id)
            .await
            .unwrap_or(0)
            >= EDITOR_LEVEL
        {
            return true;
        }
    }
    false
}

/// 注册 rag 业务条目下载授权钩子(启动期调用一次, 对齐 Python config/server.py)
pub fn register_download_grant(state: AppState) {
    module_file::config::download_grant::register_download_grant("rag", move |user_id, entry| {
        let state = state.clone();
        async move { check_entry_download_grant(state, user_id, entry.id).await }
    });
}
