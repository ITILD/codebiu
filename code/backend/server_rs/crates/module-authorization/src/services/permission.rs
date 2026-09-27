//! 权限服务(对齐 Python service/permission.py)
//!
//! 业务规则: 不存在按 404 处理(文案与 Python 一致); 权限树组装在本层;
//! 数据库读写委托 dao::permission。

use std::collections::HashMap;

use sea_orm::DatabaseConnection;

use crate::do_::entity::permission;

use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};

use crate::dao;
use crate::do_::permission::{PermissionCreate, PermissionTreeNode, PermissionUpdate};

/// 创建权限
pub async fn create(
    db: &DatabaseConnection,
    data: PermissionCreate,
) -> Result<permission::Model, AppError> {
    dao::permission::insert(db, data).await
}

/// 权限/菜单树形结构(各层按 order_num 升序)
pub async fn get_tree(
    db: &DatabaseConnection,
) -> Result<Vec<PermissionTreeNode>, AppError> {
    let perms = dao::permission::list_all(db).await?;
    Ok(build_perm_tree(perms))
}

/// 分页查询权限列表(无过滤参数, total 为权限总数; 与 Python 一致无排序)
pub async fn list_paged(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
) -> Result<PaginationResponse<permission::Model>, AppError> {
    let (items, total) = dao::permission::list_paged(db, pagination.offset(), pagination.limit()).await?;
    Ok(PaginationResponse::create(items, total as i64, pagination))
}

/// 按权限代码精确查询(不存在 404 "权限不存在")
pub async fn get_by_code(db: &DatabaseConnection, code: &str) -> Result<permission::Model, AppError> {
    dao::permission::find_by_code(db, code)
        .await?
        .ok_or_else(|| AppError::not_found("权限不存在"))
}

/// 指定父权限下的子权限列表(按 order_num 升序)
pub async fn list_by_parent(
    db: &DatabaseConnection,
    parent_id: &str,
) -> Result<Vec<permission::Model>, AppError> {
    dao::permission::list_by_parent(db, parent_id).await
}

/// 按ID获取权限(不存在 404 "权限不存在")
pub async fn get(db: &DatabaseConnection, permission_id: &str) -> Result<permission::Model, AppError> {
    dao::permission::get(db, permission_id)
        .await?
        .ok_or_else(|| AppError::not_found("权限不存在"))
}

/// 部分更新权限(不存在 404)
pub async fn update(
    db: &DatabaseConnection,
    permission_id: &str,
    data: PermissionUpdate,
) -> Result<(), AppError> {
    let model = dao::permission::get(db, permission_id)
        .await?
        .ok_or_else(|| AppError::not_found(format!("未找到ID为 {permission_id} 的权限")))?;
    dao::permission::update(db, model, data).await?;
    Ok(())
}

/// 删除权限(不存在 404; 不做子权限级联校验)
pub async fn delete(db: &DatabaseConnection, permission_id: &str) -> Result<(), AppError> {
    if !dao::permission::delete(db, permission_id).await? {
        return Err(AppError::not_found(format!(
            "未找到ID为 {permission_id} 的权限"
        )));
    }
    Ok(())
}

/// 构建权限树(输入已按 order_num 升序, 字段对齐 Python PermissionTree)
fn build_perm_tree(all: Vec<permission::Model>) -> Vec<PermissionTreeNode> {
    let mut nodes: HashMap<String, PermissionTreeNode> = all
        .iter()
        .map(|p| {
            (
                p.id.clone(),
                PermissionTreeNode {
                    id: p.id.clone(),
                    parent_id: p.parent_id.clone(),
                    name: p.name.clone(),
                    code: p.code.clone(),
                    menu_type: p.menu_type.clone(),
                    perms: p.perms.clone(),
                    icon: p.icon.clone(),
                    order_num: p.order_num,
                    visible: p.visible,
                    is_active: p.is_active,
                    children: Vec::new(),
                },
            )
        })
        .collect();
    let mut roots: Vec<PermissionTreeNode> = Vec::new();
    for p in &all {
        let is_root = p
            .parent_id
            .as_ref()
            .map(|pid| pid.is_empty() || pid == "0")
            .unwrap_or(true);
        let node = nodes.remove(&p.id).expect("树节点已初始化");
        if is_root {
            roots.push(node);
        } else if let Some(parent) = p.parent_id.as_ref().and_then(|pid| nodes.get_mut(pid)) {
            parent.children.push(node);
        } else {
            // 父权限缺失的孤儿节点提升为根, 避免数据丢失
            roots.push(node);
        }
    }
    roots.sort_by_key(|n| n.order_num);
    roots
}
