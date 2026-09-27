//! 部门数据访问(对齐 Python dao/dept.py)
//!
//! 仅做数据库读写; 父部门存在性/重名校验与树形组装在 services 层。

use sea_orm::{ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, PaginatorTrait, QueryFilter, QueryOrder, Set};
use uuid::Uuid;

use crate::do_::entity::dept;

use common::utils::error::AppError;

use crate::do_::now_utc;
use crate::do_::dept::DeptCreate;
use crate::do_::dept::DeptUpdate;

/// 按ID查询部门
pub async fn get(db: &DatabaseConnection, dept_id: &str) -> Result<Option<dept::Model>, AppError> {
    Ok(dept::Entity::find_by_id(dept_id).one(db).await?)
}

/// 按名称查询部门(重名校验用)
pub async fn find_by_name(
    db: &DatabaseConnection,
    name: &str,
) -> Result<Option<dept::Model>, AppError> {
    Ok(dept::Entity::find()
        .filter(dept::Column::Name.eq(name))
        .one(db)
        .await?)
}

/// 统计指定父部门下的子部门数量
pub async fn count_children(
    db: &DatabaseConnection,
    parent_id: &str,
) -> Result<u64, AppError> {
    let count = dept::Entity::find()
        .filter(dept::Column::ParentId.eq(parent_id))
        .count(db)
        .await?;
    Ok(count)
}

/// 计算父链 ancestors(父存在取其祖先链拼接; 父缺失按 "0", 与 Python dao 行为一致)
pub async fn calc_ancestors(
    db: &DatabaseConnection,
    parent_id: &str,
) -> Result<String, AppError> {
    if parent_id.is_empty() || parent_id == "0" {
        return Ok("0".to_string());
    }
    let parent = dept::Entity::find_by_id(parent_id).one(db).await?;
    Ok(match parent {
        Some(p) if !p.ancestors.is_empty() => format!("{},{}", p.ancestors, p.id),
        Some(p) => p.id,
        None => "0".to_string(),
    })
}

/// 插入部门记录(ancestors 由调用方计算后传入; 字段缺省值与 Python Dept 模型一致)
pub async fn insert(
    db: &DatabaseConnection,
    data: DeptCreate,
    ancestors: String,
) -> Result<dept::Model, AppError> {
    let now = now_utc();
    let am = dept::ActiveModel {
        parent_id: Set(Some(data.parent_id)),
        ancestors: Set(ancestors),
        name: Set(data.name),
        order_num: Set(data.order_num.unwrap_or(0)),
        leader: Set(data.leader),
        phone: Set(data.phone),
        email: Set(data.email),
        is_active: Set(data.is_active.unwrap_or(true)),
        id: Set(Uuid::new_v4().simple().to_string()),
        created_at: Set(Some(now)),
        updated_at: Set(now),
    };
    Ok(am.insert(db).await?)
}

/// 部分更新部门记录(仅显式传入字段生效; 传非空 parent_id 时自动重算 ancestors)
pub async fn update(
    db: &DatabaseConnection,
    model: dept::Model,
    data: DeptUpdate,
) -> Result<dept::Model, AppError> {
    let mut am: dept::ActiveModel = model.into();
    // 修改 parent_id 时重算 ancestors(Python: 传非空 parent_id 才重算)
    if let Some(parent_id) = data.parent_id {
        am.parent_id = Set(Some(parent_id.clone()));
        if !parent_id.is_empty() {
            am.ancestors = Set(calc_ancestors(db, &parent_id).await?);
        }
    }
    if let Some(v) = data.ancestors {
        am.ancestors = Set(v);
    }
    if let Some(v) = data.name {
        am.name = Set(v);
    }
    if let Some(v) = data.order_num {
        am.order_num = Set(v);
    }
    if let Some(v) = data.leader {
        am.leader = Set(Some(v));
    }
    if let Some(v) = data.phone {
        am.phone = Set(Some(v));
    }
    if let Some(v) = data.email {
        am.email = Set(Some(v));
    }
    if let Some(v) = data.is_active {
        am.is_active = Set(v);
    }
    am.updated_at = Set(now_utc());
    Ok(am.update(db).await?)
}

/// 删除部门记录(返回是否实际删除)
pub async fn delete(db: &DatabaseConnection, dept_id: &str) -> Result<bool, AppError> {
    let result = dept::Entity::delete_by_id(dept_id).exec(db).await?;
    Ok(result.rows_affected > 0)
}

/// 全部部门(按 order_num 升序, 供扁平列表与树形组装)
pub async fn list_all(db: &DatabaseConnection) -> Result<Vec<dept::Model>, AppError> {
    Ok(dept::Entity::find()
        .order_by_asc(dept::Column::OrderNum)
        .all(db)
        .await?)
}
