//! 角色表同步辅助(声明 upsert; 运行期 CRUD 在 services/role.rs)
//!
//! 声明字段变化时更新, 否则跳过写库; 数据库读写委托 dao::role。

use sea_orm::DatabaseConnection;

use common::utils::error::AppError;

use crate::dao;
use crate::do_::role::{RoleCreate, RoleUpdate};

/// 内置角色声明行(仅声明管理的字段)
pub struct RoleRow {
    pub name: &'static str,
    pub role_key: &'static str,
    pub description: &'static str,
    pub sort: i32,
}

/// 按 role_key 幂等写入内置角色(声明字段变化时更新, 否则跳过)
pub async fn upsert_builtin(db: &DatabaseConnection, role_def: &RoleRow) -> Result<(), AppError> {
    let existing = dao::role::find_by_key(db, role_def.role_key).await?;
    match existing {
        Some(model) => {
            let changed = model.name != role_def.name
                || model.description.as_deref() != Some(role_def.description)
                || model.sort != role_def.sort;
            if changed {
                // 仅更新声明管理字段(role_key/data_scope/is_active 不动)
                dao::role::update(
                    db,
                    model,
                    RoleUpdate {
                        name: Some(role_def.name.to_string()),
                        description: Some(role_def.description.to_string()),
                        sort: Some(role_def.sort),
                        ..Default::default()
                    },
                )
                .await?;
            }
            Ok(())
        }
        None => {
            // 默认值与 Python Role 模型一致: data_scope="1", is_active=true
            dao::role::insert(
                db,
                RoleCreate {
                    name: role_def.name.to_string(),
                    role_key: role_def.role_key.to_string(),
                    description: Some(role_def.description.to_string()),
                    sort: Some(role_def.sort),
                    data_scope: None,
                    is_active: None,
                },
            )
            .await?;
            Ok(())
        }
    }
}
