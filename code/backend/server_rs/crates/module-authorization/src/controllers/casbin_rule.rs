//! casbin 权限规则控制器(对齐 Python controller/casbin_rule.py)
//!
//! 路由前缀 /authorization/casbin-rules: 策略/角色绑定 CRUD、批量授权、
//! 模块声明树与角色节点级权限全量同步。响应格式与 Python 逐字段对齐。

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::Json;
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::HashSet;

use crate::casbin_mgr::auth;
use crate::deps::{authorize, AuthUser};
use crate::do_::casbin_rule::{
    BatchRolePermissionsRequest, BatchUserRolesRequest, CheckPermissionRequest, MessageData,
    PolicyRule, RolePermsRequest, RolePermsResult, RoleUserRequest,
};
use crate::do_::permission::PermissionCheckResponse;
use crate::perms;
use common::utils::extract::{AppJson, AppQuery};
use common::runtime::AppState;
use common::utils::error::AppError;
use crate::do_::entity::user;

/// sys:casbin 资源权限校验
async fn require_perm(user: &user::Model, act: &str) -> Result<(), AppError> {
    authorize(&user.id, "sys", "casbin", act).await
}

/// 写操作失败统一兜底(casbin 写入异常 → 500, 与 Python 异常捕获后返回 false 不同,
/// 此处保留错误信息便于排查; 正常路径语义一致)
fn casbin_err_msg(e: String) -> AppError {
    AppError::Internal(format!("策略操作失败: {e}"))
}

/// POST /policy —— 新增策略规则(201; 已存在 400 "策略规则已存在")
pub async fn add_policy(
    State(_state): State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(req): AppJson<PolicyRule>,
) -> Result<(StatusCode, Json<Value>), AppError> {
    require_perm(&actor, "create").await?;
    let added = auth()
        .add_policy(vec![req.sub.clone(), req.dom.clone(), req.obj.clone(), req.act.clone()])
        .await
        .map_err(casbin_err_msg)?;
    if !added {
        return Err(AppError::business("策略规则已存在"));
    }
    Ok((
        StatusCode::CREATED,
        Json(json!({ "message": "策略规则添加成功", "data": req })),
    ))
}

/// DELETE /policy —— 按四元组精确删除策略(规则不存在 404)
pub async fn remove_policy(
    State(_state): State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(req): AppJson<PolicyRule>,
) -> Result<Json<Value>, AppError> {
    require_perm(&actor, "delete").await?;
    let removed = auth()
        .remove_policy(vec![req.sub, req.dom, req.obj, req.act])
        .await
        .map_err(casbin_err_msg)?;
    if !removed {
        return Err(AppError::not_found("策略规则不存在"));
    }
    Ok(Json(json!({ "message": "策略规则删除成功" })))
}

/// POST /role-user —— 为用户绑定角色(201; 已拥有 400 "用户已拥有该角色")
pub async fn add_role_for_user(
    State(_state): State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(req): AppJson<RoleUserRequest>,
) -> Result<(StatusCode, Json<Value>), AppError> {
    require_perm(&actor, "create").await?;
    let added = auth()
        .add_grouping_policy(vec![req.user_id, req.role_key, req.dom])
        .await
        .map_err(casbin_err_msg)?;
    if !added {
        return Err(AppError::business("用户已拥有该角色"));
    }
    Ok((StatusCode::CREATED, Json(json!({ "message": "角色添加成功" }))))
}

/// DELETE /role-user —— 解除用户角色绑定(未拥有 404)
pub async fn remove_role_for_user(
    State(_state): State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(req): AppJson<RoleUserRequest>,
) -> Result<Json<Value>, AppError> {
    require_perm(&actor, "delete").await?;
    let removed = auth()
        .remove_grouping_policy(vec![req.user_id, req.role_key, req.dom])
        .await
        .map_err(casbin_err_msg)?;
    if !removed {
        return Err(AppError::not_found("用户未拥有该角色"));
    }
    Ok(Json(json!({ "message": "角色删除成功" })))
}

/// GET /roles/{user_id}?dom=* —— 查询用户在指定域的角色列表
pub async fn get_roles_for_user(
    State(_state): State<AppState>,
    AuthUser(actor): AuthUser,
    Path(user_id): Path<String>,
    AppQuery(dom): AppQuery<DomQuery>,
) -> Result<Json<Value>, AppError> {
    require_perm(&actor, "read").await?;
    let roles = auth().get_roles_for_user(&user_id, Some(&dom.dom)).await;
    Ok(Json(json!({ "message": "获取成功", "data": roles })))
}

/// GET /permissions/{role_key}?dom=* —— 查询角色权限([{domain, permission_code, method}])
pub async fn get_permissions_for_role(
    State(_state): State<AppState>,
    AuthUser(actor): AuthUser,
    Path(role_key): Path<String>,
    AppQuery(dom): AppQuery<DomQuery>,
) -> Result<Json<Value>, AppError> {
    require_perm(&actor, "read").await?;
    let formatted: Vec<Value> = auth()
        .get_policies(None)
        .await
        .into_iter()
        .filter(|p| p.len() >= 4 && p[0] == role_key && (p[1] == dom.dom || p[1] == "*"))
        .map(|p| json!({ "domain": p[1], "permission_code": p[2], "method": p[3] }))
        .collect();
    Ok(Json(json!({ "message": "获取成功", "data": formatted })))
}

/// POST /check-permission —— 校验用户权限(响应 {"has_permission": bool})
pub async fn check_permission(
    State(_state): State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(req): AppJson<CheckPermissionRequest>,
) -> Result<Json<PermissionCheckResponse>, AppError> {
    require_perm(&actor, "read").await?;
    let has = auth()
        .enforce(&req.user_id, &req.dom, &req.obj, &req.act)
        .await;
    Ok(Json(PermissionCheckResponse { has_permission: has }))
}

/// POST /batch-role-permissions —— 批量为角色添加权限(先清空该域已有策略再逐条写入)
pub async fn batch_add_role_permissions(
    State(_state): State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(req): AppJson<BatchRolePermissionsRequest>,
) -> Result<(StatusCode, Json<Value>), AppError> {
    require_perm(&actor, "create").await?;
    let manager = auth();
    // 先移除该角色在该域的全部策略(与 Python remove_filtered_policy(0, role_key, dom) 一致)
    manager
        .remove_filtered_policy(0, vec![req.role_key.clone(), req.dom.clone()])
        .await
        .map_err(casbin_err_msg)?;
    let mut added_count = 0;
    for perm in &req.permissions {
        let rule = vec![
            req.role_key.clone(),
            req.dom.clone(),
            perm.permission_code.clone(),
            perm.method.clone(),
        ];
        if manager.add_policy(rule).await.map_err(casbin_err_msg)? {
            added_count += 1;
        }
    }
    Ok((
        StatusCode::CREATED,
        Json(json!({ "message": format!("成功添加{added_count}个权限"), "added_count": added_count })),
    ))
}

/// POST /batch-user-roles —— 批量为用户绑定角色(先清空该域已有绑定再逐条写入)
pub async fn batch_add_user_roles(
    State(_state): State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(req): AppJson<BatchUserRolesRequest>,
) -> Result<(StatusCode, Json<Value>), AppError> {
    require_perm(&actor, "create").await?;
    let manager = auth();
    manager
        .remove_filtered_grouping_policy(0, vec![req.user_id.clone(), req.dom.clone()])
        .await
        .map_err(casbin_err_msg)?;
    let mut added_count = 0;
    for role_key in &req.role_keys {
        let rule = vec![req.user_id.clone(), role_key.clone(), req.dom.clone()];
        if manager
            .add_grouping_policy(rule)
            .await
            .map_err(casbin_err_msg)?
        {
            added_count += 1;
        }
    }
    Ok((
        StatusCode::CREATED,
        Json(json!({ "message": format!("成功添加{added_count}个角色"), "added_count": added_count })),
    ))
}

/// DELETE /role-permissions/{role_key}?dom=* —— 清空角色权限(返回删除数量)
pub async fn delete_role_permissions(
    State(_state): State<AppState>,
    AuthUser(actor): AuthUser,
    Path(role_key): Path<String>,
    AppQuery(dom): AppQuery<DomQuery>,
) -> Result<Json<Value>, AppError> {
    require_perm(&actor, "delete").await?;
    let manager = auth();
    // 先统计再删除(与 Python: get_filtered_policy 计数 → remove_filtered_policy 一致)
    let deleted_count = manager
        .get_policies(None)
        .await
        .into_iter()
        .filter(|p| p.len() >= 4 && p[0] == role_key && p[1] == dom.dom)
        .count();
    manager
        .remove_filtered_policy(0, vec![role_key, dom.dom])
        .await
        .map_err(casbin_err_msg)?;
    Ok(Json(json!({
        "message": format!("成功删除{deleted_count}个权限"),
        "deleted_count": deleted_count
    })))
}

/// DELETE /user-roles/{user_id}?dom=* —— 清空用户角色(返回删除数量)
pub async fn delete_user_roles(
    State(_state): State<AppState>,
    AuthUser(actor): AuthUser,
    Path(user_id): Path<String>,
    AppQuery(dom): AppQuery<DomQuery>,
) -> Result<Json<Value>, AppError> {
    require_perm(&actor, "delete").await?;
    let manager = auth();
    let deleted_count = manager
        .get_roles_for_user(&user_id, Some(&dom.dom))
        .await
        .len();
    manager
        .remove_filtered_grouping_policy(0, vec![user_id, dom.dom])
        .await
        .map_err(casbin_err_msg)?;
    Ok(Json(json!({
        "message": format!("成功删除{deleted_count}个角色"),
        "deleted_count": deleted_count
    })))
}

/// POST /reload-policy —— 从数据库重载策略
pub async fn reload_policy(
    State(_state): State<AppState>,
    AuthUser(actor): AuthUser,
) -> Result<Json<Value>, AppError> {
    require_perm(&actor, "update").await?;
    auth().reload_policy().await.map_err(casbin_err_msg)?;
    Ok(Json(json!({ "message": "策略规则重新加载成功" })))
}

/// GET /policies?dom= —— 全部策略规则(可按域过滤; 命中该域或全局 "*" 的规则)
pub async fn get_all_policies(
    State(_state): State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(dom): AppQuery<OptionalDomQuery>,
) -> Result<Json<Value>, AppError> {
    require_perm(&actor, "read").await?;
    let policies: Vec<Vec<String>> = auth()
        .get_policies(None)
        .await
        .into_iter()
        .filter(|p| match &dom.dom {
            Some(d) => p.len() >= 4 && (p[1] == *d || p[1] == "*"),
            None => true,
        })
        .collect();
    Ok(Json(json!({ "message": "获取成功", "data": policies })))
}

/// GET /grouping-policies?dom= —— 全部用户-角色绑定(可按域过滤)
pub async fn get_all_grouping_policies(
    State(_state): State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(dom): AppQuery<OptionalDomQuery>,
) -> Result<Json<Value>, AppError> {
    require_perm(&actor, "read").await?;
    let policies: Vec<Vec<String>> = auth()
        .get_grouping_policies(None)
        .await
        .into_iter()
        .filter(|p| match &dom.dom {
            Some(d) => p.len() >= 3 && (p[2] == *d || p[2] == "*"),
            None => true,
        })
        .collect();
    Ok(Json(json!({ "message": "获取成功", "data": policies })))
}

/// GET /module-tree —— 模块权限声明树(角色授权界面的可分配权限集合)
pub async fn get_module_permission_tree(
    State(_state): State<AppState>,
    AuthUser(actor): AuthUser,
) -> Result<Json<Value>, AppError> {
    require_perm(&actor, "read").await?;
    let tree: Vec<Value> = perms::get_all()
        .iter()
        .map(|define| {
            json!({
                "name": define.name,
                "code": define.module,
                "menu_type": "M",
                "icon": define.icon,
                "order_num": define.order_num,
                "children": node_to_json(define.nodes),
            })
        })
        .collect();
    Ok(Json(json!({ "message": "获取成功", "data": tree })))
}

/// 声明节点 → 前端树结构(字段与 Python _node_to_dict 一致)
fn node_to_json(nodes: &'static [perms::PermNode]) -> Vec<Value> {
    nodes
        .iter()
        .map(|node| {
            json!({
                "name": node.name,
                "code": node.code,
                "menu_type": node.menu_type,
                "path": node.path,
                "icon": node.icon,
                "order_num": node.order_num,
                "children": node_to_json(node.children),
            })
        })
        .collect()
}

/// GET /role-perms/{role_key} —— 角色已授权的节点级权限码(勾选回显)
pub async fn get_role_node_codes(
    State(_state): State<AppState>,
    AuthUser(actor): AuthUser,
    Path(role_key): Path<String>,
) -> Result<Json<Value>, AppError> {
    require_perm(&actor, "read").await?;
    let node_set: HashSet<(String, String, String)> =
        perms::iter_node_policies().into_iter().collect();
    let codes: Vec<String> = auth()
        .get_policies(None)
        .await
        .into_iter()
        .filter(|p| p.len() >= 4 && p[0] == role_key)
        .map(|p| (p[1].clone(), p[2].clone(), p[3].clone()))
        .collect::<HashSet<_>>()
        .into_iter()
        .filter(|key| node_set.contains(key))
        .map(|(dom, obj, act)| format!("{dom}:{obj}:{act}"))
        .collect();
    Ok(Json(json!({ "message": "获取成功", "data": codes })))
}

/// POST /role-perms —— 全量同步角色节点级权限(收回未勾选 + 授予新勾选)
pub async fn sync_role_permissions(
    State(_state): State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(req): AppJson<RolePermsRequest>,
) -> Result<Json<MessageData<RolePermsResult>>, AppError> {
    require_perm(&actor, "update").await?;
    let manager = auth();
    // 勾选的权限码 → (dom, obj, act) 集合(忽略目录/菜单级权限码)
    let selected: HashSet<(String, String, String)> = req
        .codes
        .iter()
        .filter_map(|code| perms::parse_perm_code(code))
        .map(|(d, o, a)| (d.to_string(), o.to_string(), a.to_string()))
        .collect();
    // 全部模块声明的节点级策略集合(可分配权限的边界)
    let node_set: HashSet<(String, String, String)> =
        perms::iter_node_policies().into_iter().collect();
    // 该角色当前全部策略中属于节点级的部分
    let existing: HashSet<(String, String, String)> = manager
        .get_policies(None)
        .await
        .into_iter()
        .filter(|p| p.len() >= 4 && p[0] == req.role_key)
        .map(|p| (p[1].clone(), p[2].clone(), p[3].clone()))
        .collect();

    let mut result = RolePermsResult { removed: 0, added: 0 };
    // 收回: 已拥有节点权限但未勾选
    for key in existing.intersection(&node_set) {
        if !selected.contains(key) {
            manager
                .remove_policy(vec![req.role_key.clone(), key.0.clone(), key.1.clone(), key.2.clone()])
                .await
                .map_err(casbin_err_msg)?;
            result.removed += 1;
        }
    }
    // 授予: 勾选但尚未拥有
    for key in selected.difference(&existing) {
        if node_set.contains(key)
            && manager
                .add_policy(vec![req.role_key.clone(), key.0.clone(), key.1.clone(), key.2.clone()])
                .await
                .map_err(casbin_err_msg)?
        {
            result.added += 1;
        }
    }
    Ok(Json(MessageData::with_message(
        &format!(
            "权限同步完成,收回 {} 条,新增 {} 条",
            result.removed, result.added
        ),
        result,
    )))
}

/// dom 查询参数(必填语义, 默认 "*")
#[derive(Debug, Deserialize)]
pub struct DomQuery {
    #[serde(default = "default_dom")]
    pub dom: String,
}

/// dom 查询参数(可选语义, 不传返回全部)
#[derive(Debug, Deserialize)]
pub struct OptionalDomQuery {
    #[serde(default)]
    pub dom: Option<String>,
}

fn default_dom() -> String {
    "*".to_string()
}

/// casbin 规则路由(挂载到 /authorization/casbin-rules)
pub fn router() -> axum::Router<common::runtime::AppState> {
    use axum::routing::{delete, get, post};
    axum::Router::new()
        .route("/policy", post(add_policy).delete(remove_policy))
        .route("/role-user", post(add_role_for_user).delete(remove_role_for_user))
        .route("/roles/{user_id}", get(get_roles_for_user))
        .route("/permissions/{role_key}", get(get_permissions_for_role))
        .route("/check-permission", post(check_permission))
        .route("/batch-role-permissions", post(batch_add_role_permissions))
        .route("/batch-user-roles", post(batch_add_user_roles))
        .route("/role-permissions/{role_key}", delete(delete_role_permissions))
        .route("/user-roles/{user_id}", delete(delete_user_roles))
        .route("/reload-policy", post(reload_policy))
        .route("/policies", get(get_all_policies))
        .route("/grouping-policies", get(get_all_grouping_policies))
        .route("/module-tree", get(get_module_permission_tree))
        .route("/role-perms", post(sync_role_permissions))
        .route("/role-perms/{role_key}", get(get_role_node_codes))
}
