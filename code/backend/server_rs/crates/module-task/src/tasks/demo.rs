//! 示例消费任务(对齐 Python module_task/tasks/demo.py)
//!
//! 模拟文档处理流水线, 演示任务队列的完整生命周期: 排队(pending) → 执行(running) → 成功/失败。
//! 与 Python 的差异: 本 crate 执行器契约只接收 (db, payload, user_id) 并返回成功/失败,
//! 分阶段进度回写由执行框架统一处理, 故此处简化为整段模拟耗时。

use sea_orm::DatabaseConnection;
use serde_json::Value;
use std::time::Duration;

/// 模拟耗时下限(秒; 与 Python max(2.0, ...) 一致)
const MIN_DURATION: f64 = 2.0;
/// 模拟耗时上限(秒; 安全上限, 防御异常 payload 长时间占用执行资源)
const MAX_DURATION: f64 = 3600.0;

/// 示例文档处理执行器(读取 payload 模拟流水线耗时后成功收尾)
///
/// payload 约定: file_name 文档名 / total_pages 页数 / duration 模拟耗时(秒)
pub async fn run_demo(
    _db: DatabaseConnection,
    payload: Value,
    _user_id: Option<String>,
) -> Result<(), String> {
    let file_name = payload
        .get("file_name")
        .and_then(Value::as_str)
        .unwrap_or("未命名文档");
    let total_pages = payload
        .get("total_pages")
        .and_then(Value::as_i64)
        .unwrap_or(20)
        .max(1);
    let duration = payload
        .get("duration")
        .and_then(Value::as_f64)
        .unwrap_or(16.0)
        .clamp(MIN_DURATION, MAX_DURATION);
    tracing::info!("示例任务开始处理: {file_name}({total_pages} 页, 模拟 {duration}s)");
    tokio::time::sleep(Duration::from_secs_f64(duration)).await;
    tracing::info!("示例任务处理完成: {file_name}");
    Ok(())
}
