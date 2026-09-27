//! 部门服务(对齐 Python service/dept.py)
//!
//! 业务规则: 父部门不存在 404、同级重名 409、存在子部门禁止删除、
//! 不存在按 404 处理(文案与 Python 一致); 部门树组装在本层;
//! 数据库读写委托 dao::dept。

use std::collections::HashMap;

use sea_orm::DatabaseConnection;

use crate::do_::entity::dept;

use common::utils::error::AppError;

use crate::dao;
use crate::do_::dept::{DeptCreate, DeptTreeNode, DeptUpdate};

/// 创建部门(父部门不存在 404; 重名 409)
pub async fn create(db: &DatabaseConnection, data: DeptCreate) -> Result<dept::Model, AppError> {
    // 父部门存在性校验(parent_id 非空且非 "0" 时)
    let has_parent = !data.parent_id.is_empty() && data.parent_id != "0";
    if has_parent && dao::dept::get(db, &data.parent_id).await?.is_none() {
        return Err(AppError::not_found(format!(
            "父部门ID {} 不存在",
            data.parent_id
        )));
    }
    // 同级部门名称重复校验(409)
    if dao::dept::find_by_name(db, &data.name).await?.is_some() {
        return Err(AppError::Conflict(format!(
            "部门名称 '{}' 已存在",
            data.name
        )));
    }
    let ancestors = dao::dept::calc_ancestors(db, &data.parent_id).await?;
    dao::dept::insert(db, data, ancestors).await
}

/// 部门树形结构(各层按 order_num 升序, 孤儿节点提升为根)
pub async fn get_tree(db: &DatabaseConnection) -> Result<Vec<DeptTreeNode>, AppError> {
    let depts = dao::dept::list_all(db).await?;
    Ok(build_dept_tree(depts))
}

/// 全部部门扁平列表(按 order_num 升序)
pub async fn list_all(db: &DatabaseConnection) -> Result<Vec<dept::Model>, AppError> {
    dao::dept::list_all(db).await
}

/// 按ID获取部门(不存在 404)
pub async fn get(db: &DatabaseConnection, dept_id: &str) -> Result<dept::Model, AppError> {
    dao::dept::get(db, dept_id)
        .await?
        .ok_or_else(|| AppError::not_found(format!("未找到ID为 {dept_id} 的部门")))
}

/// 删除部门(存在子部门 400; 不存在 404; 不做级联删除)
pub async fn delete(db: &DatabaseConnection, dept_id: &str) -> Result<(), AppError> {
    if dao::dept::count_children(db, dept_id).await? > 0 {
        return Err(AppError::business("存在子部门，不允许删除"));
    }
    if !dao::dept::delete(db, dept_id).await? {
        return Err(AppError::not_found(format!("未找到ID为 {dept_id} 的部门")));
    }
    Ok(())
}

/// 部分更新部门(不存在 404; 调整 parent_id 时自动重算 ancestors)
pub async fn update(db: &DatabaseConnection, dept_id: &str, data: DeptUpdate) -> Result<(), AppError> {
    let model = dao::dept::get(db, dept_id)
        .await?
        .ok_or_else(|| AppError::not_found(format!("未找到ID为 {dept_id} 的部门")))?;
    dao::dept::update(db, model, data).await?;
    Ok(())
}

/// 构建部门树(输入已按 order_num 升序, children 插入序即排序结果)
fn build_dept_tree(all: Vec<dept::Model>) -> Vec<DeptTreeNode> {
    let mut nodes: HashMap<String, DeptTreeNode> = all
        .iter()
        .map(|d| {
            (
                d.id.clone(),
                DeptTreeNode {
                    id: d.id.clone(),
                    parent_id: d.parent_id.clone(),
                    name: d.name.clone(),
                    order_num: d.order_num,
                    leader: d.leader.clone(),
                    phone: d.phone.clone(),
                    email: d.email.clone(),
                    is_active: d.is_active,
                    children: Vec::new(),
                },
            )
        })
        .collect();
    let mut roots: Vec<DeptTreeNode> = Vec::new();
    for d in &all {
        let is_root = d
            .parent_id
            .as_ref()
            .map(|p| p.is_empty() || p == "0")
            .unwrap_or(true);
        let node = nodes.remove(&d.id).expect("树节点已初始化");
        if is_root {
            roots.push(node);
        } else if let Some(parent) = d.parent_id.as_ref().and_then(|pid| nodes.get_mut(pid)) {
            parent.children.push(node);
        } else {
            // 父部门缺失的孤儿节点提升为根, 避免数据丢失(与 Python 行为一致)
            roots.push(node);
        }
    }
    roots.sort_by_key(|n| n.order_num);
    roots
}
