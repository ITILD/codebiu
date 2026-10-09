//! sys_config 表行读写(对齐 Python config/dynamic/dao.py 的 SysConfigDao)
//!
//! 纯 DB 层: 只做行级存取, 不含缓存/校验/打码语义(那些在 service.rs)。

use chrono::Utc;
use sea_orm::{ActiveModelTrait, DatabaseConnection, EntityTrait, Set};
use serde_json::Value;

use crate::do_::entity::sys_config;
use crate::AppResult;

/// 按组标识取配置行, 不存在返回 None(对齐 SysConfigDao.get)
pub async fn find_row(
    db: &DatabaseConnection,
    group: &str,
) -> AppResult<Option<sys_config::Model>> {
    Ok(sys_config::Entity::find_by_id(group).one(db).await?)
}

/// 按组写配置: 不存在则建行(version=1), 存在则覆盖 value 且 version+1
/// (对齐 SysConfigDao.upsert)
pub async fn upsert_row(
    db: &DatabaseConnection,
    group: &str,
    value: &Value,
    updated_by: Option<&str>,
) -> AppResult<()> {
    let existing = find_row(db, group).await?;
    let now = Utc::now().fixed_offset();
    match existing {
        Some(row) => {
            let new_version = row.version + 1;
            let mut am: sys_config::ActiveModel = row.into();
            am.value = Set(Some(value.clone()));
            am.version = Set(new_version);
            if let Some(by) = updated_by {
                am.updated_by = Set(Some(by.to_string()));
            }
            am.updated_at = Set(now);
            am.update(db).await?;
        }
        None => {
            sys_config::ActiveModel {
                group: Set(group.to_string()),
                value: Set(Some(value.clone())),
                version: Set(1),
                updated_by: Set(updated_by.map(|s| s.to_string())),
                updated_at: Set(now),
            }
            .insert(db)
            .await?;
        }
    }
    Ok(())
}
