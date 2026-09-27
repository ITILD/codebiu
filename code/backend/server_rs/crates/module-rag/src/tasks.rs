//! module-rag 任务执行器注册(对齐 Python module_rag/tasks/)
//!
//! 本地执行器经 module-task 的 IoC 注册表注入; 任务类型名照抄 Python
//! ("rag_document_parse"/"rag_revectorize"), 任务生命周期(认领/终态回写)由
//! module-task 执行框架统一负责, 执行器只关心业务本身。
//!
//! 说明: LocalTaskRunner 签名不含 task_id, 故执行器内部不做 task_queue.progress
//! 细粒度回写(与 Python worker 的 PROGRESS 事件存在口径偏差, 见模块报告)。

use std::sync::Arc;

use common::runtime::AppState;
use module_task::tasks::LocalTaskRunner;

use crate::services::document as doc_svc;
use crate::services::permission::enforce_project_permission;

/// 注册 rag 本地任务执行器(app 启动期建表后调用一次)
pub fn init_task_runners(state: AppState) {
    // 文档解析任务("上传即解析"/手动解析共用)
    let parse_state = state.clone();
    let parse_runner: LocalTaskRunner = Arc::new(move |db, payload, user_id| {
        let state = parse_state.clone();
        Box::pin(async move { run_document_parse(state, db, payload, user_id).await })
    });
    module_task::tasks::register_local_runner("rag_document_parse", parse_runner);

    // 全库重向量化任务(向量库引擎未实现 → 执行体返回失败描述)
    let revec_state = state.clone();
    let revec_runner: LocalTaskRunner = Arc::new(move |db, payload, user_id| {
        let state = revec_state.clone();
        Box::pin(async move { run_revectorize(state, db, payload, user_id).await })
    });
    module_task::tasks::register_local_runner("rag_revectorize", revec_runner);
}

/// 从任务参数中读取字符串字段
fn payload_str(payload: &serde_json::Value, key: &str) -> String {
    payload
        .get(key)
        .and_then(serde_json::Value::as_str)
        .unwrap_or_default()
        .to_string()
}

/// 文档解析任务执行体: 复检项目内 update 档位 → 解析管线(解析→分块→向量化→落表)
async fn run_document_parse(
    state: AppState,
    _db: sea_orm::DatabaseConnection,
    payload: serde_json::Value,
    user_id: Option<String>,
) -> Result<(), String> {
    let document_id = payload_str(&payload, "document_id");
    let user_id = user_id.unwrap_or_default();
    if document_id.is_empty() {
        return Err("任务参数缺少 document_id".to_string());
    }
    let run = async {
        let document = doc_svc::get_document(&state, &document_id).await?;
        // worker 以创建者身份执行, 复检文档所属项目的 update 档位
        enforce_project_permission(&state, &user_id, &document.project_id, "doc", "update").await?;
        doc_svc::parse_document(&state, &document_id, &user_id, None).await?;
        Ok::<(), common::utils::error::AppError>(())
    };
    run.await.map_err(|e| e.to_string())
}

/// 全库重向量化任务执行体: 管理员复检 → 执行体(向量库引擎未实现 → 失败)
async fn run_revectorize(
    state: AppState,
    _db: sea_orm::DatabaseConnection,
    payload: serde_json::Value,
    user_id: Option<String>,
) -> Result<(), String> {
    let user_id = user_id.unwrap_or_default();
    // 仅系统管理员可执行(controller 已拦截, worker 侧复检防绕过)
    if !module_authorization::casbin_mgr::auth().is_global_admin(&user_id).await {
        return Err("仅系统管理员可执行全库重向量化".to_string());
    }
    let model_id = payload
        .get("model_id")
        .and_then(serde_json::Value::as_str)
        .map(str::to_string);
    doc_svc::revectorize_all(&state, model_id).await
}
