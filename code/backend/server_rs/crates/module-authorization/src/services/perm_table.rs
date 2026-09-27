//! 权限表同步辅助(按 code upsert; 运行期 CRUD 在 services/permission.rs)
//!
//! 声明字段无变化时跳过写库; 数据库读写委托 dao::permission。

use sea_orm::DatabaseConnection;

use common::utils::error::AppError;

use crate::dao;
use crate::do_::permission::PermissionCreate;

/// 权限声明行(仅声明管理的字段)
pub struct PermissionRow {
    pub name: &'static str,
    pub code: &'static str,
    pub menu_type: &'static str,
    pub description: Option<&'static str>,
    pub path: Option<&'static str>,
    pub icon: Option<&'static str>,
    pub order_num: i32,
    pub visible: bool,
    /// 父节点 ID("0" 为根)
    pub parent_id: String,
}

/// 按 code 幂等写入权限声明, 返回记录 ID(声明字段无变化时跳过写库)
pub async fn upsert(db: &DatabaseConnection, row: &PermissionRow) -> Result<String, AppError> {
    let existing = dao::permission::find_by_code(db, row.code).await?;
    match existing {
        Some(model) => {
            let model_id = model.id.clone();
            let changed = model.name != row.name
                || model.menu_type != row.menu_type
                || model.description.as_deref() != row.description
                || model.path.as_deref() != row.path
                || model.icon.as_deref() != row.icon
                || model.order_num != row.order_num
                || model.visible != row.visible
                || model.parent_id.as_deref() != Some(row.parent_id.as_str());
            if changed {
                dao::permission::update_declaration(
                    db,
                    model,
                    row.name,
                    row.menu_type,
                    row.description,
                    row.path,
                    row.icon,
                    row.order_num,
                    row.visible,
                    &row.parent_id,
                )
                .await?;
            }
            Ok(model_id)
        }
        None => {
            // component/perms 置空, is_active 默认 true(与 Python Permission 模型一致)
            let inserted = dao::permission::insert(
                db,
                PermissionCreate {
                    parent_id: Some(row.parent_id.clone()),
                    name: row.name.to_string(),
                    code: row.code.to_string(),
                    description: row.description.map(|s| s.to_string()),
                    menu_type: row.menu_type.to_string(),
                    path: row.path.map(|s| s.to_string()),
                    component: None,
                    perms: None,
                    icon: row.icon.map(|s| s.to_string()),
                    order_num: Some(row.order_num),
                    visible: Some(row.visible),
                    is_active: None,
                },
            )
            .await?;
            Ok(inserted.id)
        }
    }
}
