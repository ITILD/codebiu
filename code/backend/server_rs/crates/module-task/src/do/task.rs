//! 任务队列 DO 层(对齐 Python module_task/do/task.py 的 DTO 部分)
//!
//! 表模型见 do/entity/task_queue.rs; 本文件定义状态常量、请求/响应 DTO 与校验辅助。

use chrono::Utc;
use common::utils::error::AppError;
use sea_orm::prelude::{DateTimeWithTimeZone, Json};
use serde::{Deserialize, Serialize};

use crate::do_::entity::task_queue;

// ############################# 状态常量(对齐 Python QueueTaskStatus StrEnum) #############################

/// 已创建等待调度(排队中)
pub const STATUS_PENDING: &str = "pending";
/// 执行中
pub const STATUS_RUNNING: &str = "running";
/// 成功完成
pub const STATUS_SUCCESS: &str = "success";
/// 执行失败(异常/超时)
pub const STATUS_FAILED: &str = "failed";
/// 被用户主动取消
pub const STATUS_CANCELLED: &str = "cancelled";
/// Celery 侧撤销(与 cancelled 区分来源)
pub const STATUS_REVOKED: &str = "revoked";

/// 非终态判断(对齐 Python ACTIVE_STATUSES: pending/running 视为活跃任务)
pub fn is_active_status(status: &str) -> bool {
    matches!(status, STATUS_PENDING | STATUS_RUNNING)
}

/// 当前 UTC 时间(实体时间戳填充用)
pub fn now_utc() -> DateTimeWithTimeZone {
    Utc::now().into()
}

/// 夹紧优先级到 0~9 区间(数值越大越优先; 与 Python _clamp_priority 一致)
pub fn clamp_priority(priority: i32) -> i32 {
    priority.clamp(0, 9)
}

/// 字符串长度上限校验(FastAPI max_length 等价, 违规 → 422)
pub fn check_max_len(loc: &[&str], value: &str, max: usize) -> Result<(), AppError> {
    if value.chars().count() > max {
        return Err(AppError::validation(
            loc,
            format!("String should have at most {max} characters"),
        ));
    }
    Ok(())
}

// ############################# 请求 DTO #############################

/// 创建任务请求(字段与 Python TaskQueueCreate 一致)
#[derive(Debug, Clone, Deserialize)]
pub struct TaskQueueCreateReq {
    /// 任务名称(≤200)
    pub name: String,
    /// 任务类型(需在 TASK_TYPES 注册表中, ≤50)
    pub task_type: String,
    /// 任务参数 JSON(缺省 {}; 必须为对象)
    #[serde(default)]
    pub payload: Option<Json>,
    /// 优先级(0~9, 越界自动夹紧)
    #[serde(default)]
    pub priority: i32,
}

// ############################# 响应 DTO #############################

/// 任务详情响应(字段与 Python TaskQueueResponse 完全一致)
///
/// 纯任务管理约定: 不透出业务信息(payload 参数/result 结果留在库中由业务模块自用),
/// 仅暴露执行情况(状态/进度/阶段描述/失败原因/时间线)。
#[derive(Debug, Clone, Serialize)]
pub struct TaskQueueResp {
    pub id: String,
    pub name: String,
    pub task_type: String,
    pub priority: i32,
    pub status: String,
    pub progress: f64,
    pub message: Option<String>,
    pub error: Option<String>,
    pub celery_task_id: Option<String>,
    /// Celery 结果后端侧状态(Rust 未实现 celery, 恒为 null; 前端契约保留字段)
    pub celery_state: Option<String>,
    /// Celery 侧回传百分比(Rust 未实现 celery, 恒为 null)
    pub celery_progress: Option<f64>,
    /// PROGRESS 时的完整进度元数据(Rust 未实现 celery, 恒为 null)
    pub celery_meta: Option<Json>,
    pub started_at: Option<DateTimeWithTimeZone>,
    pub finished_at: Option<DateTimeWithTimeZone>,
    pub created_at: Option<DateTimeWithTimeZone>,
    pub updated_at: DateTimeWithTimeZone,
}

impl From<task_queue::Model> for TaskQueueResp {
    fn from(m: task_queue::Model) -> Self {
        Self {
            id: m.id,
            name: m.name,
            task_type: m.task_type,
            priority: m.priority,
            status: m.status,
            progress: m.progress,
            message: m.message,
            error: m.error,
            celery_task_id: m.celery_task_id,
            celery_state: None,
            celery_progress: None,
            celery_meta: None,
            started_at: m.started_at,
            finished_at: m.finished_at,
            created_at: m.created_at,
            updated_at: m.updated_at,
        }
    }
}

/// 任务状态统计(轮询刷新概览卡片; 对齐 Python TaskStatsResponse)
#[derive(Debug, Clone, Default, Serialize)]
pub struct TaskStatsResp {
    pub total: i64,
    pub pending: i64,
    pub running: i64,
    pub success: i64,
    pub failed: i64,
    pub cancelled: i64,
}

/// 任务类型定义响应(字段与 Python TaskTypeDef 完全一致)
#[derive(Debug, Clone, Serialize)]
pub struct TaskTypeDefResp {
    pub r#type: String,
    pub name: String,
    pub description: String,
    pub celery_task: String,
    /// local 引擎执行器标记(Python 返回 "模块:函数" 路径; Rust 执行器经 IoC 注入,
    /// 已注册时为 "local", 未注册时为 null)
    pub local_runner: Option<String>,
    pub default_payload: Json,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn 状态活跃判断与python口径一致() {
        assert!(is_active_status(STATUS_PENDING));
        assert!(is_active_status(STATUS_RUNNING));
        assert!(!is_active_status(STATUS_SUCCESS));
        assert!(!is_active_status(STATUS_FAILED));
        assert!(!is_active_status(STATUS_CANCELLED));
        assert!(!is_active_status(STATUS_REVOKED));
    }

    #[test]
    fn 优先级越界自动夹紧() {
        assert_eq!(clamp_priority(-5), 0);
        assert_eq!(clamp_priority(5), 5);
        assert_eq!(clamp_priority(99), 9);
    }

    #[test]
    fn 长度超限返回422校验错误() {
        assert!(check_max_len(&["body", "name"], "a", 200).is_ok());
        let err = check_max_len(&["body", "name"], &"x".repeat(201), 200).unwrap_err();
        assert_eq!(err.status_code(), axum::http::StatusCode::UNPROCESSABLE_ENTITY);
    }
}
