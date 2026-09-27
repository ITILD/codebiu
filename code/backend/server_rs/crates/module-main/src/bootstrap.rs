//! 启动引导: 字典种子批量幂等同步(对齐 Python dict_seed.ensure_default_dicts)
//!
//! 两次 SELECT 拉取现有数据 → 内存 diff → 批量插入缺失记录。
//! 只补缺不更新不删除: 管理员在界面的修改不会被覆盖。重复启动安全。

use std::collections::{HashMap, HashSet};

use sea_orm::{ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, QueryFilter, Set};
use tracing::{error, info};

use crate::dict_seed::SEEDS;
use crate::do_::entity::{dict_item, dict_type};

/// 将注册中心的字典种子声明幂等同步到 dict_type/dict_item 表(建表后启动钩子调用)
pub async fn ensure_default_dicts(db: &DatabaseConnection) {
    if SEEDS.is_empty() {
        info!("无字典种子声明,跳过初始化");
        return;
    }
    if let Err(e) = sync(db).await {
        error!("字典种子同步失败: {e}");
    }
}

/// 种子同步主流程(错误向上抛, 由入口统一记录)
async fn sync(db: &DatabaseConnection) -> Result<(), sea_orm::DbErr> {
    let type_codes: Vec<String> = SEEDS.iter().map(|s| s.type_code.to_string()).collect();

    // 批量查缺 1): 现有字典类型(type_code -> 记录)
    let rows = dict_type::Entity::find()
        .filter(dict_type::Column::TypeCode.is_in(type_codes))
        .all(db)
        .await?;
    let existing_types: HashMap<String, dict_type::Model> =
        rows.into_iter().map(|t| (t.type_code.clone(), t)).collect();

    // 批量查缺 2): 现有字典项((type_id, item_code) 集合), 仅查种子类型的
    let type_ids: Vec<String> = existing_types.values().map(|t| t.id.clone()).collect();
    let mut existing_items: HashSet<(String, String)> = HashSet::new();
    if !type_ids.is_empty() {
        let items = dict_item::Entity::find()
            .filter(dict_item::Column::DictTypeId.is_in(type_ids))
            .all(db)
            .await?;
        existing_items = items
            .into_iter()
            .map(|i| (i.dict_type_id, i.item_code))
            .collect();
    }

    // 内存 diff + 批量插入
    let mut added_types = 0i32;
    let mut added_items = 0i32;
    for (type_idx, seed) in SEEDS.iter().enumerate() {
        let type_id = match existing_types.get(seed.type_code) {
            Some(t) => t.id.clone(),
            None => {
                // 新类型: id 即时生成, 供字典项引用(对齐 Python default_factory)
                let id = uuid::Uuid::new_v4().simple().to_string();
                let sort_order = if seed.sort_order != 0 { seed.sort_order } else { type_idx as i32 + 1 };
                dict_type::ActiveModel {
                    id: Set(id.clone()),
                    type_code: Set(seed.type_code.to_string()),
                    type_name: Set(seed.type_name.to_string()),
                    description: Set(seed.description.map(str::to_string)),
                    is_active: Set(true),
                    sort_order: Set(sort_order),
                    created_at: Set(Some(chrono::Utc::now().fixed_offset())),
                    updated_at: Set(chrono::Utc::now().fixed_offset()),
                }
                .insert(db)
                .await?;
                added_types += 1;
                id
            }
        };
        for (item_idx, item) in seed.items.iter().enumerate() {
            if existing_items.contains(&(type_id.clone(), item.item_code.to_string())) {
                continue;
            }
            let sort_order = if item.sort_order != 0 { item.sort_order } else { item_idx as i32 + 1 };
            dict_item::ActiveModel {
                id: Set(uuid::Uuid::new_v4().simple().to_string()),
                dict_type_id: Set(type_id.clone()),
                item_code: Set(item.item_code.to_string()),
                item_name: Set(item.item_name.to_string()),
                item_value: Set(item.item_value.map(str::to_string)),
                description: Set(item.description.map(str::to_string)),
                is_active: Set(true),
                sort_order: Set(sort_order),
                created_at: Set(Some(chrono::Utc::now().fixed_offset())),
                updated_at: Set(chrono::Utc::now().fixed_offset()),
            }
            .insert(db)
            .await?;
            added_items += 1;
        }
    }

    if added_types + added_items > 0 {
        info!("字典种子同步完成: 新增类型 {added_types} 个, 字典项 {added_items} 条");
    } else {
        info!("基础字典完整,无需补写");
    }
    Ok(())
}
