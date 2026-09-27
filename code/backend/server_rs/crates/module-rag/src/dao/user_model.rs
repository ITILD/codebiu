//! 用户-模型绑定 DAO(对齐 Python module_rag/dao/user_model.py)

use sea_orm::{
    ActiveModelTrait, ColumnTrait, DatabaseConnection, DbErr, EntityTrait, IntoActiveModel,
    QueryFilter, Set,
};

use crate::do_::entity::user_model;

/// 按用户获取绑定记录
pub async fn get_by_user(
    db: &DatabaseConnection,
    user_id: &str,
) -> Result<Option<user_model::Model>, DbErr> {
    user_model::Entity::find()
        .filter(user_model::Column::UserId.eq(user_id))
        .one(db)
        .await
}

/// 新增绑定记录
pub async fn add(db: &DatabaseConnection, am: user_model::ActiveModel) -> Result<user_model::Model, DbErr> {
    am.insert(db).await
}

/// 按用户更新绑定(仅 Some 字段, 需先存在记录)
pub async fn update_by_user(
    db: &DatabaseConnection,
    user_id: &str,
    chat_model_id: Option<Option<String>>,
    embedding_model_id: Option<Option<String>>,
    rerank_model_id: Option<Option<String>>,
    asr_model_id: Option<Option<String>>,
    tts_model_id: Option<Option<String>>,
    vad_model_id: Option<Option<String>>,
    denoise_model_id: Option<Option<String>>,
    fallback_disabled: Option<bool>,
) -> Result<(), DbErr> {
    let Some(existing) = user_model::Entity::find()
        .filter(user_model::Column::UserId.eq(user_id))
        .one(db)
        .await?
    else {
        return Ok(());
    };
    let mut am = existing.into_active_model();
    if let Some(v) = chat_model_id {
        am.chat_model_id = Set(v);
    }
    if let Some(v) = embedding_model_id {
        am.embedding_model_id = Set(v);
    }
    if let Some(v) = rerank_model_id {
        am.rerank_model_id = Set(v);
    }
    if let Some(v) = asr_model_id {
        am.asr_model_id = Set(v);
    }
    if let Some(v) = tts_model_id {
        am.tts_model_id = Set(v);
    }
    if let Some(v) = vad_model_id {
        am.vad_model_id = Set(v);
    }
    if let Some(v) = denoise_model_id {
        am.denoise_model_id = Set(v);
    }
    if let Some(v) = fallback_disabled {
        am.fallback_disabled = Set(v);
    }
    am.updated_at = Set(chrono::Utc::now().into());
    am.update(db).await?;
    Ok(())
}
