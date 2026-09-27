//! 模型配置服务层(对齐 Python module_ai/service/model_config.py)
//!
//! 职责: scope 规整与校验 / url 协议白名单 / 默认公共模型唯一性 / 敏感信息脱敏 /
//! 后台自动校验调度 / 启动期 default_models 补种(init_hooks)。

use chrono::{DateTime, FixedOffset, Utc};
use serde_json::{json, Value};
use sea_orm::DatabaseConnection;

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::{
    InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse,
};

use crate::do_::entity::model_config as entity;
use crate::do_::model_config::{ModelConfigCreate, ModelConfigResp, ModelConfigUpdate, ModelScope};
use crate::dao::model_config as dao;
use crate::services::llm;

/// UTC 时区偏移(DateTimeWithTimeZone 构造用)
fn utc_tz() -> FixedOffset {
    chrono::FixedOffset::east_opt(0).expect("UTC 偏移合法")
}

// ############################# 校验与规整 #############################

/// 校验 url 协议白名单(http/https) + 可选域名黑名单(配置 model_url_domain_blacklist)
///
/// None/空串跳过; 违反时构造业务错误(400)
fn validate_url(url: Option<&str>) -> Result<(), AppError> {
    let Some(url) = url.filter(|u| !u.trim().is_empty()) else {
        return Ok(());
    };
    let lowered = url.trim().to_lowercase();
    if !lowered.starts_with("http://") && !lowered.starts_with("https://") {
        return Err(AppError::business(format!(
            "模型 url 仅支持 http/https 协议: {url}"
        )));
    }
    // 可选域名黑名单(走配置节, 未配置则不启用; 读取失败跳过校验)
    let Some(blacklist) = common::config::raw_json()
        .get("model_url_domain_blacklist")
        .and_then(Value::as_array)
    else {
        return Ok(());
    };
    let hits = blacklist
        .iter()
        .filter_map(Value::as_str)
        .map(|d| d.trim().to_lowercase())
        .any(|d| !d.is_empty() && lowered.contains(&d));
    if hits {
        return Err(AppError::business(format!("模型 url 命中禁用域名: {url}")));
    }
    Ok(())
}

/// scope 与 dept_id/is_default 一致性校验与规整
///
/// 部门模型必须指定归属部门; 个人/公共模型清空部门; 默认标记仅对 public 生效
fn normalize_scope(create: &mut ModelConfigCreate) -> Result<(), AppError> {
    match create.scope {
        ModelScope::Dept => {
            if create
                .dept_id
                .as_deref()
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .is_none()
            {
                return Err(AppError::business("部门模型必须指定归属部门(dept_id)"));
            }
        }
        _ => create.dept_id = None,
    }
    if create.is_default && create.scope != ModelScope::Public {
        create.dept_id = None;
    }
    Ok(())
}

/// 保证该模型类型的默认公共模型唯一: 已有旧默认且不是当前记录时取消其默认标记
async fn ensure_default_unique(
    db: &DatabaseConnection,
    model_type: &str,
    current_id: Option<&str>,
) -> Result<(), AppError> {
    let current = dao::get_default_by_type(db, model_type, false).await?;
    if let Some(current) = current {
        if Some(current.id.as_str()) != current_id {
            dao::update(
                db,
                &current.id,
                &ModelConfigUpdate {
                    is_default: Some(false),
                    ..Default::default()
                },
            )
            .await?;
        }
    }
    Ok(())
}

/// 更新未显式改 scope 时, 判断该记录当前是否仍为 public(默认标记语义延续)
async fn becomes_public_default(db: &DatabaseConnection, id: &str) -> Result<bool, AppError> {
    Ok(dao::get(db, id)
        .await?
        .map(|m| m.scope == "public")
        .unwrap_or(false))
}

/// 模型配置写操作审计日志(logging 起步; 私有/部门模型记录归属与去向, 公共模型免审计)
fn audit_log(action: &str, scope: &str, model: &str, user_id: &str, dept_id: Option<&str>) {
    if scope == "public" {
        return;
    }
    tracing::info!(
        "[模型审计] {action} scope={scope} model={model} owner={user_id} dept={}",
        dept_id.unwrap_or("")
    );
}

// ############################# 写操作 #############################

/// 添加新的模型配置(允许同名, 以来源/配置区分)
///
/// 校验 scope 一致性与 url 协议白名单; 设置默认公共模型时先取消旧默认;
/// 私有/部门模型写操作记审计日志; 写库后调度后台自动校验并回写结果。
pub async fn add(
    db: &DatabaseConnection,
    http: &reqwest::Client,
    mut create: ModelConfigCreate,
) -> Result<String, AppError> {
    normalize_scope(&mut create)?;
    validate_url(create.url.as_deref())?;
    // 设置默认公共模型时, 先取消该类型旧的默认标记, 保证唯一
    if create.scope == ModelScope::Public && create.is_default {
        ensure_default_unique(db, &create.model_type, None).await?;
    }
    let model_id = dao::add(db, create.clone()).await?;
    audit_log(
        "create",
        create.scope.as_str(),
        &create.model,
        &create.user_id,
        create.dept_id.as_deref(),
    );
    schedule_check(db.clone(), http.clone(), model_id.clone());
    Ok(model_id)
}

/// 删除模型配置(先取原记录供审计, 再物理删除)
pub async fn delete(db: &DatabaseConnection, id: &str) -> Result<(), AppError> {
    let existing = dao::get(db, id).await?;
    dao::delete(db, id).await?;
    if let Some(existing) = existing {
        audit_log(
            "delete",
            &existing.scope,
            &existing.model,
            &existing.user_id,
            existing.dept_id.as_deref(),
        );
    }
    Ok(())
}

/// 更新补丁是否包含任一有效字段(空补丁不触发 DAO 更新与重新校验)
fn patch_has_updates(patch: &ModelConfigUpdate) -> bool {
    patch.clear_dept_id
        || patch.model_type.is_some()
        || patch.server_type.is_some()
        || patch.model.is_some()
        || patch.url.is_some()
        || patch.api_key.is_some()
        || patch.scope.is_some()
        || patch.dept_id.is_some()
        || patch.is_default.is_some()
        || patch.is_active.is_some()
        || patch.display_name.is_some()
        || patch.pay_in.is_some()
        || patch.pay_out.is_some()
        || patch.input_tokens.is_some()
        || patch.out_tokens.is_some()
        || patch.temperature.is_some()
        || patch.timeout.is_some()
        || patch.no_think.is_some()
        || patch.extra.is_some()
        || patch.check_valid.is_some()
        || patch.check_format.is_some()
        || patch.checked_at.is_some()
        || patch.check_result.is_some()
}

/// 更新模型配置
///
/// url/api_key 为空值(None/空串)时跳过更新, 防止前端携带脱敏后的空值覆盖真实密钥;
/// scope 切换时回填/清空部门; 默认公共模型保持唯一; 变更后重新调度后台校验。
pub async fn update(
    db: &DatabaseConnection,
    http: &reqwest::Client,
    model_config_id: &str,
    mut patch: ModelConfigUpdate,
) -> Result<(), AppError> {
    // 空值保护: 前端编辑被脱敏的模型时 url/api_key 会以空值回传, 不覆盖真实值
    if patch.url.as_deref().map(str::is_empty).unwrap_or(false) {
        patch.url = None;
    }
    if patch
        .api_key
        .as_deref()
        .map(str::is_empty)
        .unwrap_or(false)
    {
        patch.api_key = None;
    }
    let mut clear_dept_id = false;
    if let Some(scope) = patch.scope {
        match scope {
            ModelScope::Dept if patch.dept_id.is_none() => {
                // 更新时若切换为部门但未带部门, 回填当前已存部门
                if let Some(existing) = dao::get(db, model_config_id).await? {
                    if existing.scope == "dept" {
                        patch.dept_id = existing.dept_id;
                    } else {
                        clear_dept_id = true;
                    }
                }
            }
            ModelScope::Dept => {}
            // 个人/公共模型不携带部门
            _ => clear_dept_id = true,
        }
    }
    patch.clear_dept_id = clear_dept_id;
    // 默认公共模型唯一性(更新未显式改 scope 时按库中记录判断)
    if patch.is_default == Some(true)
        && (patch.scope == Some(ModelScope::Public)
            || (patch.scope.is_none() && becomes_public_default(db, model_config_id).await?))
    {
        if let Some(existing) = dao::get(db, model_config_id).await? {
            // model_type 未随本次提交时回退库中已有类型
            let model_type = patch.model_type.clone().unwrap_or(existing.model_type);
            ensure_default_unique(db, &model_type, Some(model_config_id)).await?;
        }
    }
    if let Some(url) = patch.url.as_deref() {
        validate_url(Some(url))?;
    }
    if patch_has_updates(&patch) {
        dao::update(db, model_config_id, &patch).await?;
        // 配置变更后重新校验并回写结果
        schedule_check(db.clone(), http.clone(), model_config_id.to_string());
    }
    // 审计: 以更新后完整记录为准
    if let Some(existing) = dao::get(db, model_config_id).await? {
        audit_log(
            "update",
            &existing.scope,
            &existing.model,
            &existing.user_id,
            existing.dept_id.as_deref(),
        );
    }
    Ok(())
}

// ############################# 读操作 #############################

/// 获取单个模型配置
pub async fn get(
    db: &DatabaseConnection,
    id: &str,
) -> Result<Option<entity::Model>, AppError> {
    dao::get(db, id).await
}

/// 分页获取模型配置列表(支持多字段过滤 + 当前用户可见性)
#[allow(clippy::too_many_arguments)]
pub async fn list_paged(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
    model: Option<&str>,
    model_type: Option<&str>,
    server_type: Option<&str>,
    scope: Option<&str>,
    user_id: Option<&str>,
    dept_id: Option<&str>,
    is_admin: bool,
    filter_user_ids: Option<&[String]>,
) -> Result<PaginationResponse<entity::Model>, AppError> {
    let items = dao::list_paged(
        db,
        pagination,
        model,
        model_type,
        server_type,
        scope,
        user_id,
        dept_id,
        is_admin,
        filter_user_ids,
    )
    .await?;
    let total = dao::count(
        db,
        model,
        model_type,
        server_type,
        scope,
        user_id,
        dept_id,
        is_admin,
        filter_user_ids,
    )
    .await?;
    Ok(PaginationResponse::create(items, total, pagination))
}

/// 滚动加载模型配置列表(带可见性过滤)
pub async fn get_scroll(
    db: &DatabaseConnection,
    params: &InfiniteScrollParams,
    user_id: Option<&str>,
    dept_id: Option<&str>,
    is_admin: bool,
) -> Result<InfiniteScrollResponse<entity::Model>, AppError> {
    let items = dao::get_scroll(db, params, user_id, dept_id, is_admin).await?;
    Ok(InfiniteScrollResponse::create(
        items,
        params.limit,
        params.direction,
        |m| m.id.clone(),
    ))
}

/// 敏感信息脱敏(就地修改):
/// - 全局管理员: 运维需要账号/密码明文, 一律不脱敏
/// - 其他用户: 仅本人私有模型(scope=user 且 user_id==本人)保留明文
pub fn mask_secrets(configs: &mut [entity::Model], user_id: &str, is_admin: bool) {
    if is_admin {
        return;
    }
    for config in configs {
        let is_owner_private = config.scope == "user" && config.user_id == user_id;
        if !is_owner_private {
            config.url = None;
            config.api_key = None;
        }
    }
}

/// 脱敏单个模型配置(详情接口复用)
pub fn mask_secret(config: &mut entity::Model, user_id: &str, is_admin: bool) {
    mask_secrets(std::slice::from_mut(config), user_id, is_admin);
}

/// 获取指定模型的默认参数kv(基于工厂配置字段默认值, 对齐 Python get_default_params)
pub async fn get_default_params(_model_name: &str) -> Result<Value, AppError> {
    Ok(json!({
        "pay_in": 0.0,
        "pay_out": 0.0,
        "input_tokens": 8192,
        "out_tokens": 8192,
        "temperature": 0.7,
        "timeout": 60,
        "no_think": false,
    }))
}

/// 仅回写能力测试明细(直连 DAO, 不走 update 流程避免重复触发自动校验)
pub async fn persist_check_result(
    db: &DatabaseConnection,
    model_config_id: &str,
    check_result: Value,
) -> Result<(), AppError> {
    dao::update(
        db,
        model_config_id,
        &ModelConfigUpdate {
            check_result: Some(check_result),
            ..Default::default()
        },
    )
    .await
}

// ############################# 后台自动校验 #############################

/// 调度后台连通性校验任务(不阻塞保存接口, 结果回写后前端展示能力标签)
pub fn schedule_check(db: DatabaseConnection, http: reqwest::Client, model_config_id: String) {
    tokio::spawn(async move {
        if let Err(e) = check_and_persist(&db, &http, &model_config_id).await {
            tracing::warn!("模型配置后台校验失败[{model_config_id}]: {e}");
        }
    });
}

/// 后台校验模型配置并把结果回写(check_valid/check_format/checked_at/check_result)
async fn check_and_persist(
    db: &DatabaseConnection,
    http: &reqwest::Client,
    id: &str,
) -> Result<(), AppError> {
    let Some(config) = dao::get(db, id).await? else {
        return Ok(());
    };
    // 仅自动校验文本类模型(ocr/asr/tts 本地语音类暂无在线测试)
    let type_key = config.model_type.clone();
    if !matches!(type_key.as_str(), "chat" | "embeddings" | "rerank") {
        return Ok(());
    }
    let items = llm::run_capability_tests(http, &config, None).await?;
    let now = Utc::now();
    // 由能力测试结果推导旧校验字段(check_valid/check_format)
    let mut is_valid: Option<bool> = None;
    let mut is_format: Option<bool> = None;
    let find_ok = |cap: &str| items.iter().find(|i| i.capability == cap).map(|i| i.ok);
    match type_key.as_str() {
        "chat" => {
            is_valid = find_ok("chat");
            is_format = find_ok("structured");
        }
        "embeddings" => is_valid = find_ok("embedding"),
        "rerank" => is_valid = find_ok("rerank"),
        _ => {}
    }
    let check_result: Value = Value::Object(
        items
            .iter()
            .map(|item| {
                (
                    item.capability.clone(),
                    json!({
                        "capability": item.capability,
                        "label": item.label,
                        "ok": item.ok,
                        "detail": item.detail,
                        "error": item.error,
                        "elapsed": item.elapsed,
                        "checked_at": now.to_rfc3339(),
                    }),
                )
            })
            .collect(),
    );
    dao::update(
        db,
        id,
        &ModelConfigUpdate {
            check_valid: is_valid,
            // check_format 仅对 chat 类型有意义
            check_format: if type_key == "chat" { is_format } else { None },
            check_result: Some(check_result),
            checked_at: Some(DateTime::<Utc>::from(now).with_timezone(&utc_tz())),
            ..Default::default()
        },
    )
    .await?;
    tracing::info!(
        "模型配置后台校验完成: {} valid={is_valid:?} format={is_format:?}",
        config.model
    );
    Ok(())
}

// ############################# 启动期 Seed(init_hooks) #############################

/// seed 支持的配置字段白名单(ModelConfigCreate 字段 - 模型类型/归属/开关类字段)
const SEED_ALLOWED_FIELDS: [&str; 14] = [
    "server_type",
    "model",
    "url",
    "api_key",
    "dept_id",
    "display_name",
    "pay_in",
    "pay_out",
    "input_tokens",
    "out_tokens",
    "temperature",
    "timeout",
    "no_think",
    "extra",
];

/// 从配置文件读取默认公共模型配置(default_models 节)
///
/// :return: (reset_models 总开关, [(model_type, 配置节)]); 未配置返回 (false, 空)
fn load_default_models_config() -> (bool, Vec<(String, Value)>) {
    let Some(raw) = common::config::raw_json().get("default_models") else {
        return (false, vec![]);
    };
    let Some(map) = raw.as_object() else {
        return (false, vec![]);
    };
    // reset_model(reset_models) 为布尔总开关(false=启动不做任何处理)
    let reset_models = raw
        .get("reset_model")
        .or_else(|| raw.get("reset_models"))
        .and_then(Value::as_bool)
        .unwrap_or(false);
    // 布尔/None 等非法值节跳过, 避免一个无效节拖垮整个默认模型 seed
    let sections = map
        .iter()
        .filter(|(k, v)| {
            k.as_str() != "reset_model" && k.as_str() != "reset_models" && v.is_object()
        })
        .map(|(k, v)| (k.to_lowercase(), v.clone()))
        .collect();
    (reset_models, sections)
}

/// 校验 default_models 配置节名是否为合法模型类型
fn valid_model_type(name: &str) -> Option<&'static str> {
    ["chat", "embeddings", "rerank", "ocr", "asr", "tts", "vad", "denoise"]
        .iter()
        .find(|t| **t == name)
        .copied()
}

/// 获取 seed 公共模型的归属用户: 默认管理员账户(动态配置); 不存在时用 system 占位
async fn resolve_seed_owner_id(state: &AppState) -> String {
    let username = match state
        .settings
        .get::<common::config::dynamic::AdminSettings>("admin")
        .await
    {
        Ok(settings) => settings.username,
        Err(e) => {
            tracing::warn!("查询默认管理员配置失败, 公共模型归属使用 system 占位: {e}");
            return "system".to_string();
        }
    };
    match dao::get_user_by_username(&state.db, &username).await {
        Some(user) => user.id,
        None => {
            tracing::warn!("查询默认管理员 '{username}' 失败, 公共模型归属使用 system 占位");
            "system".to_string()
        }
    }
}

/// 从 seed 配置节提取白名单字段并构造创建对象(公共默认模型)
fn seed_fields_to_create(fields: &Value, model_type: &str, owner_id: &str) -> ModelConfigCreate {
    let g = |k: &str| fields.get(k);
    ModelConfigCreate {
        model_type: model_type.to_string(),
        server_type: g("server_type")
            .and_then(Value::as_str)
            .unwrap_or("openai")
            .to_string(),
        model: g("model")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string(),
        url: g("url").and_then(Value::as_str).map(str::to_string),
        api_key: g("api_key").and_then(Value::as_str).map(str::to_string),
        scope: ModelScope::Public,
        dept_id: None,
        is_default: true,
        is_active: true,
        display_name: g("display_name")
            .and_then(Value::as_str)
            .map(str::to_string),
        pay_in: g("pay_in").and_then(Value::as_f64).unwrap_or(0.0),
        pay_out: g("pay_out").and_then(Value::as_f64).unwrap_or(0.0),
        input_tokens: g("input_tokens").and_then(Value::as_i64).unwrap_or(8192) as i32,
        out_tokens: g("out_tokens").and_then(Value::as_i64).unwrap_or(8192) as i32,
        temperature: g("temperature").and_then(Value::as_f64).unwrap_or(0.7),
        timeout: g("timeout").and_then(Value::as_i64).unwrap_or(60) as i32,
        no_think: g("no_think").and_then(Value::as_bool),
        extra: g("extra").filter(|v| v.is_object()).cloned(),
        user_id: owner_id.to_string(),
    }
}

/// 判断库中默认公共模型与配置是否一致(仅比较配置中显式写出的模型字段, 数字按 f64 宽松比较)
fn config_matches(existing: &entity::Model, section: &Value) -> bool {
    let resp = ModelConfigResp::from(existing.clone());
    let Ok(resp_value) = serde_json::to_value(&resp) else {
        return false;
    };
    SEED_ALLOWED_FIELDS.iter().all(|key| match section.get(*key) {
        Some(config_value) => match resp_value.get(*key) {
            Some(actual) => json_loose_eq(actual, config_value),
            None => false,
        },
        // 配置未写出的字段不参与比较
        None => true,
    })
}

/// JSON 宽松相等(数字统一按 f64 比较, 兼容 yaml int 与 ORM Double 的类型差)
fn json_loose_eq(a: &Value, b: &Value) -> bool {
    match (a, b) {
        (Value::Number(x), Value::Number(y)) => x.as_f64() == y.as_f64(),
        _ => a == b,
    }
}

/// 语音模型 server_type 归一化迁移: dashscope→online, sherpa/qwen→local(幂等)
///
/// 历史方案值写入 extra.legacy_server_type 保留; 必须先于 ensure_default_models 执行:
/// seed 会比对 server_type, 旧值未归一化会误判"配置不一致"导致旧默认转私有 + 重复建新默认。
async fn ensure_voice_server_type(db: &DatabaseConnection) -> Result<(), AppError> {
    let rows = dao::list_legacy_voice_rows(db).await?;
    if rows.is_empty() {
        return Ok(());
    }
    let count = rows.len();
    for row in rows {
        let legacy = row.server_type.clone();
        let migrated = match legacy.as_str() {
            "dashscope" => "online",
            "sherpa" | "qwen" => "local",
            _ => continue,
        };
        // extra 防御性归一为对象后记录原方案值
        let mut extra = match row.extra {
            Some(Value::Object(map)) => Value::Object(map),
            _ => Value::Object(Default::default()),
        };
        if let Some(obj) = extra.as_object_mut() {
            obj.insert("legacy_server_type".to_string(), Value::String(legacy));
        }
        dao::update_extra_raw(db, &row.id, migrated, &extra).await?;
    }
    tracing::info!(
        "语音模型 server_type 已归一化: {count} 条记录迁移为 online/local(原值保留在 extra.legacy_server_type)"
    );
    Ok(())
}

/// 启动时按配置 default_models 节补种默认公共模型(幂等, reset_models 总开关控制)
///
/// - reset_models=false(或缺省): 什么都不做, 库中模型配置完全保留
/// - reset_models=true 且类型 enabled=true: 无默认则创建; 一致则保持;
///   不一致则旧默认转私有保留 + 按配置创建新默认
async fn ensure_default_models(state: &AppState) {
    let (reset_models, seed_config) = load_default_models_config();
    if !reset_models || seed_config.is_empty() {
        return;
    }
    let owner_id = resolve_seed_owner_id(state).await;
    for (type_name, section) in &seed_config {
        if !section.get("enabled").and_then(Value::as_bool).unwrap_or(false) {
            continue;
        }
        let Some(model_type) = valid_model_type(type_name) else {
            tracing::warn!("default_models 配置节 '{type_name}' 不是合法模型类型, 已跳过");
            continue;
        };
        if section
            .get("model")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .is_none()
        {
            tracing::warn!("default_models 配置节 '{type_name}' 缺少 model 字段, 已跳过");
            continue;
        }
        let existing = match dao::get_default_by_type(&state.db, type_name, false).await {
            Ok(v) => v,
            Err(e) => {
                tracing::error!("默认公共模型[{type_name}] seed 失败: {e}");
                continue;
            }
        };
        let outcome: Result<(), AppError> = async {
            match existing {
                None => {
                    let create = seed_fields_to_create(section, model_type, &owner_id);
                    let model_name = create.model.clone();
                    add(&state.db, &state.http, create).await?;
                    tracing::info!("默认公共模型[{type_name}] 已按配置创建: {model_name}");
                }
                Some(existing) if config_matches(&existing, section) => {
                    tracing::info!(
                        "默认公共模型[{type_name}] 与配置一致, 保持不变: {}",
                        existing.model
                    );
                }
                Some(existing) => {
                    // 与配置不一致: 旧默认转为私有保留(已绑定它的用户回退新默认), 再创建新默认
                    dao::update(
                        &state.db,
                        &existing.id,
                        &ModelConfigUpdate {
                            scope: Some(ModelScope::User),
                            is_default: Some(false),
                            ..Default::default()
                        },
                    )
                    .await?;
                    let create = seed_fields_to_create(section, model_type, &owner_id);
                    let (old_model, new_model) = (existing.model.clone(), create.model.clone());
                    add(&state.db, &state.http, create).await?;
                    tracing::info!(
                        "默认公共模型[{type_name}] 配置变更: 原默认已转私有({old_model}), 新默认已创建({new_model})"
                    );
                }
            }
            Ok(())
        }
        .await;
        if let Err(e) = outcome {
            tracing::error!("默认公共模型[{type_name}] seed 失败: {e}");
        }
    }
}

/// 模块启动初始化钩子(表结构就绪后由 app 装配调用)
pub async fn init_hooks(state: &AppState) {
    if let Err(e) = ensure_voice_server_type(&state.db).await {
        tracing::error!("语音模型 server_type 归一化迁移失败: {e}");
    }
    ensure_default_models(state).await;
}
