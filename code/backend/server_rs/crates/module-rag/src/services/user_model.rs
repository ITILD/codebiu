//! 用户-模型绑定业务服务(对齐 Python module_rag/service/user_model.py)

use common::runtime::AppState;
use common::utils::error::AppError;
use sea_orm::EntityTrait;

use crate::dao::user_model as dao;
use crate::do_::user_model::{model_type, ResolvedModel, UserModelResponse, UserModelUpdate};

/// 校验模型配置使用权限(公共/本部门/本人; 停用/越权 → 400, 不存在 → 404)
async fn validate_model_access(state: &AppState, model_id: Option<&str>, user_id: &str) -> Result<(), AppError> {
    let Some(model_id) = model_id.filter(|m| !m.is_empty()) else {
        return Ok(());
    };
    let config = module_ai::dao::model_config::get(&state.db, model_id)
        .await?
        .ok_or_else(|| AppError::not_found(format!("模型配置不存在: {model_id}")))?;
    // 停用模型视为绑定失效(触发回退链, 与前端灰色不可选语义一致)
    if !config.is_active {
        return Err(AppError::business(format!("模型配置已停用: {model_id}")));
    }
    // 公共模型放行
    if config.scope == "public" {
        return Ok(());
    }
    // 本人模型放行
    if config.scope == "user" && config.user_id.as_str() == user_id {
        return Ok(());
    }
    // 部门模型: 校验当前用户所属部门
    if config.scope == "dept" {
        if let Some(u) = module_authorization::do_::entity::user::Entity::find_by_id(user_id.to_owned())
            .one(&state.db)
            .await?
        {
            if u.dept_id.is_some() && config.dept_id.is_some() && u.dept_id == config.dept_id {
                return Ok(());
            }
        }
    }
    Err(AppError::business(format!(
        "无权使用模型配置: {model_id}(仅可用公共/本部门/自己的模型)"
    )))
}

/// 用户级回退开关(绑定失效时是否禁止回退默认公共模型)
async fn fallback_disabled(state: &AppState, user_id: &str) -> bool {
    dao::get_by_user(&state.db, user_id)
        .await
        .map(|b| b.is_some_and(|b| b.fallback_disabled))
        .unwrap_or(false)
}

/// 解析用户可用的模型(绑定 → 归属校验 → 回退开关允许时回退默认公共模型)
///
/// 结果标记是否发生回退, 供调用方在 SSE/响应中提示数据流向变化(v4 4.3)
pub async fn resolve_model(
    state: &AppState,
    user_id: &str,
    model_type: &str,
) -> Result<ResolvedModel, AppError> {
    let binding = dao::get_by_user(&state.db, user_id).await?;
    let mut model_id: Option<String> = binding.as_ref().map(|b| match model_type {
        model_type::CHAT => b.chat_model_id.clone(),
        model_type::EMBEDDINGS => b.embedding_model_id.clone(),
        model_type::RERANK => b.rerank_model_id.clone(),
        model_type::ASR => b.asr_model_id.clone(),
        model_type::TTS => b.tts_model_id.clone(),
        model_type::VAD => b.vad_model_id.clone(),
        model_type::DENOISE => b.denoise_model_id.clone(),
        _ => None,
    }).flatten();
    // binding_unset: 未设置该类型绑定(无绑定记录或该类型为空)
    let mut binding_unset = binding.is_none() || model_id.is_none();
    let mut binding_valid = false;
    if let Some(mid) = &model_id {
        // 使用时兜底校验(绑定后配置被转手/取消共享/停用的场景)
        match validate_model_access(state, Some(mid), user_id).await {
            Ok(()) => binding_valid = true,
            Err(e) => {
                tracing::warn!("用户 {user_id} {model_type} 模型绑定校验失败, 尝试默认公共模型回退: {e}");
                model_id = None;
                binding_unset = false;
            }
        }
    }
    if binding_valid {
        return Ok(ResolvedModel { model_id, fallback_used: false, binding_unset: false });
    }
    // 绑定失效/未绑定: 用户级开关允许时才回退默认公共模型
    if fallback_disabled(state, user_id).await {
        tracing::info!("用户 {user_id} 已关闭模型回退, {model_type} 绑定失效不回退");
        return Ok(ResolvedModel { model_id: None, fallback_used: false, binding_unset });
    }
    let fallback = module_ai::dao::model_config::get_default_by_type(&state.db, model_type, true)
        .await?
        .map(|m| m.id);
    if let Some(fid) = &fallback {
        tracing::info!("用户未绑定/绑定失效 {model_type} 模型, 回退使用默认公共模型: {fid}");
    }
    let fallback_used = fallback.is_some();
    Ok(ResolvedModel { model_id: fallback, fallback_used, binding_unset })
}

/// 获取用户-模型绑定响应(未绑定返回空绑定)
pub async fn get_by_user(state: &AppState, user_id: &str) -> Result<UserModelResponse, AppError> {
    Ok(match dao::get_by_user(&state.db, user_id).await? {
        Some(m) => m.into(),
        None => UserModelResponse::empty(user_id),
    })
}

/// 新增或更新用户的模型绑定
///
/// 流程: 归一化(命中默认公共模型 → 解绑) → 逐个校验归属 → 无存量且无绑定不落库
///
/// 注意: serde 无法区分"未传"与"显式 null", 二者统一按解绑(None)处理(与 Python
/// exclude_unset 语义的偏差已在模块报告注明)。
pub async fn upsert(state: &AppState, user_id: &str, req: UserModelUpdate) -> Result<UserModelResponse, AppError> {
    // 归一化: 选中"默认公共模型"视为未绑定(存 None), 管理员换默认模型后全体用户无缝跟随
    let mut req = req;
    let normalize = |model_id: &Option<String>, default_id: &Option<String>| -> Option<Option<String>> {
        match (model_id, default_id) {
            (Some(mid), Some(did)) if mid == did => Some(None),
            (Some(mid), _) => Some(Some(mid.clone())),
            (None, _) => Some(None),
        }
    };
    for (mt, slot) in [
        (model_type::CHAT, req.chat_model_id.clone()),
        (model_type::EMBEDDINGS, req.embedding_model_id.clone()),
        (model_type::RERANK, req.rerank_model_id.clone()),
        (model_type::ASR, req.asr_model_id.clone()),
        (model_type::TTS, req.tts_model_id.clone()),
        (model_type::VAD, req.vad_model_id.clone()),
        (model_type::DENOISE, req.denoise_model_id.clone()),
    ] {
        let default_id = module_ai::dao::model_config::get_default_by_type(&state.db, mt, false)
            .await?
            .map(|m| m.id);
        let normalized = normalize(&slot, &default_id);
        match mt {
            model_type::CHAT => req.chat_model_id = normalized.unwrap(),
            model_type::EMBEDDINGS => req.embedding_model_id = normalized.unwrap(),
            model_type::RERANK => req.rerank_model_id = normalized.unwrap(),
            model_type::ASR => req.asr_model_id = normalized.unwrap(),
            model_type::TTS => req.tts_model_id = normalized.unwrap(),
            model_type::VAD => req.vad_model_id = normalized.unwrap(),
            _ => req.denoise_model_id = normalized.unwrap(),
        }
    }
    // 逐个校验本次提交的模型配置归属/共享权限
    for mid in [
        req.chat_model_id.as_deref(),
        req.embedding_model_id.as_deref(),
        req.rerank_model_id.as_deref(),
        req.asr_model_id.as_deref(),
        req.tts_model_id.as_deref(),
        req.vad_model_id.as_deref(),
        req.denoise_model_id.as_deref(),
    ] {
        validate_model_access(state, mid, user_id).await?;
    }
    let existing = dao::get_by_user(&state.db, user_id).await?;
    match existing {
        Some(_) => {
            dao::update_by_user(
                &state.db,
                user_id,
                Some(req.chat_model_id),
                Some(req.embedding_model_id),
                Some(req.rerank_model_id),
                Some(req.asr_model_id),
                Some(req.tts_model_id),
                Some(req.vad_model_id),
                Some(req.denoise_model_id),
                req.fallback_disabled,
            )
            .await?;
            Ok(dao::get_by_user(&state.db, user_id).await?.map(Into::into).unwrap())
        }
        None => {
            // 无存量记录且未选择任何模型: 不选=跟随系统默认公共模型, 无需落库
            let has_binding = [
                req.chat_model_id.as_deref(),
                req.embedding_model_id.as_deref(),
                req.rerank_model_id.as_deref(),
                req.asr_model_id.as_deref(),
                req.tts_model_id.as_deref(),
                req.vad_model_id.as_deref(),
                req.denoise_model_id.as_deref(),
            ]
            .iter()
            .any(|v| v.is_some())
                || req.fallback_disabled == Some(true);
            if !has_binding {
                tracing::info!("用户 {user_id} 未选择任何模型, 跳过创建绑定记录(跟随系统默认公共模型)");
                return Ok(UserModelResponse::empty(user_id));
            }
            let id = uuid::Uuid::new_v4().simple().to_string();
            dao::add(
                &state.db,
                crate::do_::entity::user_model::ActiveModel {
                    id: sea_orm::Set(id),
                    user_id: sea_orm::Set(user_id.to_string()),
                    chat_model_id: sea_orm::Set(req.chat_model_id),
                    embedding_model_id: sea_orm::Set(req.embedding_model_id),
                    rerank_model_id: sea_orm::Set(req.rerank_model_id),
                    asr_model_id: sea_orm::Set(req.asr_model_id),
                    tts_model_id: sea_orm::Set(req.tts_model_id),
                    vad_model_id: sea_orm::Set(req.vad_model_id),
                    denoise_model_id: sea_orm::Set(req.denoise_model_id),
                    fallback_disabled: sea_orm::Set(req.fallback_disabled.unwrap_or(false)),
                    created_at: sea_orm::Set(Some(chrono::Utc::now().into())),
                    updated_at: sea_orm::Set(chrono::Utc::now().into()),
                },
            )
            .await?;
            Ok(dao::get_by_user(&state.db, user_id).await?.map(Into::into).unwrap())
        }
    }
}
