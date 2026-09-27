//! 任务队列服务层(对齐 Python module_task/service/task.py)
//!
//! 职责: 任务创建(校验注册表 → 落库 pending → 按引擎派发) / 状态查询统计 /
//!       生命周期管理(取消/重试/删除)。

use common::config::dynamic::TasksSettings;
use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};
use sea_orm::{DatabaseConnection, IntoActiveModel, Set};
use uuid::Uuid;

use crate::dao::task_dao;
use crate::do_::entity::task_queue;
use crate::do_::task::{
    clamp_priority, is_active_status, now_utc, TaskQueueCreateReq, TaskQueueResp, TaskStatsResp,
    TaskTypeDefResp, STATUS_CANCELLED, STATUS_FAILED, STATUS_PENDING, STATUS_REVOKED,
    STATUS_RUNNING, STATUS_SUCCESS,
};
use crate::tasks;

/// 任务队列服务(持应用状态; 对齐 Python TaskQueueService)
#[derive(Clone)]
pub struct TaskQueueService {
    state: AppState,
}

impl TaskQueueService {
    /// 构建服务实例
    pub fn new(state: AppState) -> Self {
        Self { state }
    }

    /// 数据库连接
    fn db(&self) -> &DatabaseConnection {
        &self.state.db
    }

    /// 取任务记录(不存在 → 404, 文案与 Python 一致)
    async fn get_required(&self, task_id: &str) -> Result<task_queue::Model, AppError> {
        task_dao::get(self.db(), task_id)
            .await?
            .ok_or_else(|| AppError::not_found(format!("未找到ID为 {task_id} 的任务")))
    }

    // ################ 查询 ################

    /// 分页查询任务列表(创建时间倒序; 过滤: keyword 模糊/status 精确/task_type 精确)
    pub async fn list_page(
        &self,
        pagination: &PaginationParams,
        keyword: Option<&str>,
        status: Option<&str>,
        task_type: Option<&str>,
    ) -> Result<PaginationResponse<TaskQueueResp>, AppError> {
        let items = task_dao::list_page(self.db(), pagination, keyword, status, task_type).await?;
        let total = task_dao::count(self.db(), keyword, status, task_type).await? as i64;
        Ok(PaginationResponse::create(
            items.into_iter().map(TaskQueueResp::from).collect(),
            total,
            pagination,
        ))
    }

    /// 查询任务详情(不存在 → 404)
    pub async fn get(&self, task_id: &str) -> Result<TaskQueueResp, AppError> {
        let task = self.get_required(task_id).await?;
        Ok(TaskQueueResp::from(task))
    }

    /// 按状态统计任务数(概览卡片/轮询; cancelled 合并 revoked, 与 Python 口径一致)
    pub async fn stats(&self) -> Result<TaskStatsResp, AppError> {
        let raw = task_dao::stats(self.db()).await?;
        Ok(stats_from_rows(raw))
    }

    /// 任务类型注册表(供前端渲染下拉与默认模板)
    pub fn registry() -> Vec<TaskTypeDefResp> {
        tasks::TASK_TYPES
            .iter()
            .map(|d| TaskTypeDefResp {
                r#type: d.r#type.to_string(),
                name: d.name.to_string(),
                description: d.description.to_string(),
                celery_task: d.celery_task.to_string(),
                // Python 返回 "模块:函数" 路径; Rust 执行器经 IoC 注入, 以 "local" 标记已注册
                local_runner: if tasks::has_local_runner(d.r#type) {
                    Some("local".to_string())
                } else {
                    None
                },
                default_payload: d.default_payload.clone(),
            })
            .collect()
    }

    // ################ 创建/投递 ################

    /// 创建任务并按引擎派发(local=进程内后台协程 / celery=未实现, 派发即失败)
    ///
    /// :return: 任务ID(Python 响应契约 response_model=str)
    pub async fn create(&self, req: TaskQueueCreateReq, user_id: &str) -> Result<String, AppError> {
        // payload 规范化: 缺省 {}; 非对象 → 422(pydantic dict 校验口径, 先于 service 的 400 校验)
        let payload = match req.payload {
            None => serde_json::json!({}),
            Some(v) if v.is_object() => v,
            Some(_) => {
                return Err(AppError::validation(
                    &["body", "payload"],
                    "Input should be a valid dictionary",
                ))
            }
        };
        // 类型必须已在注册表(400, 文案与 Python 一致)
        if tasks::get_task_type(&req.task_type).is_none() {
            let registered = tasks::task_type_names().join(", ");
            return Err(AppError::business(format!(
                "任务类型 {} 未注册(可用类型: {})",
                req.task_type, registered
            )));
        }
        let task_id = Uuid::new_v4().simple().to_string();
        let am = task_queue::ActiveModel {
            // 32 位小写 hex uuid, 与 Python uuid4().hex 一致
            id: Set(task_id.clone()),
            name: Set(req.name),
            task_type: Set(req.task_type),
            payload: Set(payload),
            priority: Set(clamp_priority(req.priority)),
            user_id: Set(user_id.to_string()),
            status: Set(STATUS_PENDING.to_string()),
            progress: Set(0.0),
            message: Set(None),
            result: Set(None),
            error: Set(None),
            celery_task_id: Set(None),
            started_at: Set(None),
            finished_at: Set(None),
            created_at: Set(Some(now_utc())),
            updated_at: Set(now_utc()),
        };
        task_dao::add(self.db(), am).await?;
        // 双引擎统一派发(仅传任务ID, 参数由执行侧从库中读取)
        self.dispatch(&task_id).await?;
        Ok(task_id)
    }

    // ################ 状态同步 ################

    /// 以 Celery 结果后端为准校正数据库状态(worker 回写中断时使用)
    ///
    /// Rust 侧 celery 未实现, celery_task_id 恒为空, Python 的校正分支自然跳过,
    /// 行为与 Python 无 celery_task_id 时一致(仅读取并返回当前状态)。
    pub async fn sync_from_celery(&self, task_id: &str) -> Result<TaskQueueResp, AppError> {
        let task = self.get_required(task_id).await?;
        Ok(TaskQueueResp::from(task))
    }

    // ################ 生命周期 ################

    /// 取消任务(非终态才可取消): 置 cancelled, 执行中的任务经终态保护自然停止回写
    pub async fn cancel(&self, task_id: &str) -> Result<(), AppError> {
        let task = self.get_required(task_id).await?;
        if !is_active_status(&task.status) {
            return Err(AppError::business(format!(
                "任务已结束({}), 无法取消",
                task.status
            )));
        }
        // Python 先 revoke Celery 侧再落库; Rust 无 celery, 直接落库
        let mut am = task.into_active_model();
        am.status = Set(STATUS_CANCELLED.to_string());
        am.message = Set(Some("任务已取消".to_string()));
        am.finished_at = Set(Some(now_utc()));
        task_dao::update(self.db(), am).await?;
        Ok(())
    }

    /// 重试任务(仅终态任务): 重置进度后按引擎重新派发
    pub async fn retry(&self, task_id: &str) -> Result<TaskQueueResp, AppError> {
        let task = self.get_required(task_id).await?;
        if is_active_status(&task.status) {
            return Err(AppError::business("任务仍在进行中, 无需重试"));
        }
        if tasks::get_task_type(&task.task_type).is_none() {
            return Err(AppError::business(format!(
                "任务类型 {} 已从注册表移除, 无法重试",
                task.task_type
            )));
        }
        // 重置字段并先落库再派发(后台协程依赖库中状态; 修复 Python 先派发后落库的竞态)
        let mut am = task.into_active_model();
        am.status = Set(STATUS_PENDING.to_string());
        am.progress = Set(0.0);
        am.message = Set(None);
        am.result = Set(None);
        am.error = Set(None);
        am.finished_at = Set(None);
        am.celery_task_id = Set(None);
        task_dao::update(self.db(), am).await?;
        // 按引擎重新派发(celery 引擎派发失败时已在 dispatch 内回写失败状态)
        self.dispatch(task_id).await?;
        let task = self.get_required(task_id).await?;
        Ok(TaskQueueResp::from(task))
    }

    /// 删除任务记录(任何状态均可删除)
    pub async fn delete(&self, task_id: &str) -> Result<(), AppError> {
        task_dao::delete(self.db(), task_id).await
    }

    // ################ 双引擎统一派发 ################

    /// 双引擎统一派发: local 引擎进程内后台执行; celery 引擎未实现 → 回写失败状态并返回 400
    ///
    /// 派发失败回写与错误文案对齐 Python create/retry 的 except 分支。
    async fn dispatch(&self, task_id: &str) -> Result<(), AppError> {
        let settings: TasksSettings = self.state.settings.get("tasks").await?;
        if settings.engine == "celery" {
            let exc = "celery 引擎暂未实现(Rust 服务仅支持 local 引擎)";
            // 派发不可用: 标记失败并保留记录, 前端可见失败原因
            if let Some(task) = task_dao::get(self.db(), task_id).await? {
                let mut am = task.into_active_model();
                am.status = Set(STATUS_FAILED.to_string());
                am.error = Set(Some(format!("任务派发失败: {exc}")));
                am.finished_at = Set(Some(now_utc()));
                task_dao::update(self.db(), am).await?;
            }
            return Err(AppError::business(format!(
                "任务派发失败, 请检查任务配置(celery 引擎需检查 Redis 与 worker): {exc}"
            )));
        }
        // local 引擎: 进程内后台协程执行(与 Celery 共用同一任务主体)
        tasks::spawn_local_task(self.state.db.clone(), task_id.to_string());
        Ok(())
    }
}

/// 分组统计行 → 统计响应(total 为全部状态之和; cancelled 合并 revoked)
fn stats_from_rows(rows: Vec<(String, i64)>) -> TaskStatsResp {
    let mut resp = TaskStatsResp::default();
    for (status, num) in rows {
        match status.as_str() {
            STATUS_PENDING => resp.pending += num,
            STATUS_RUNNING => resp.running += num,
            STATUS_SUCCESS => resp.success += num,
            STATUS_FAILED => resp.failed += num,
            STATUS_CANCELLED | STATUS_REVOKED => resp.cancelled += num,
            _ => {}
        }
        resp.total += num;
    }
    resp
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn 分组统计聚合口径与python一致() {
        let resp = stats_from_rows(vec![
            ("pending".to_string(), 2),
            ("running".to_string(), 1),
            ("success".to_string(), 4),
            ("failed".to_string(), 1),
            ("cancelled".to_string(), 2),
            ("revoked".to_string(), 1),
        ]);
        assert_eq!(resp.total, 11);
        assert_eq!(resp.pending, 2);
        assert_eq!(resp.running, 1);
        assert_eq!(resp.success, 4);
        assert_eq!(resp.failed, 1);
        // cancelled 合并 revoked
        assert_eq!(resp.cancelled, 3);
    }

    #[test]
    fn 注册表响应字段与python一致() {
        let defs = TaskQueueService::registry();
        assert_eq!(defs.len(), 3);
        let demo = defs.iter().find(|d| d.r#type == "demo_document").unwrap();
        assert_eq!(demo.name, "示例: 文档处理");
        assert_eq!(demo.celery_task, "task.run_demo_document");
        // 内置示例执行器已注册
        assert_eq!(demo.local_runner.as_deref(), Some("local"));
        assert_eq!(demo.default_payload["file_name"], "示例文档.pdf");
        // rag 类型未注入执行器 → null
        let rag = defs.iter().find(|d| d.r#type == "rag_revectorize").unwrap();
        assert!(rag.local_runner.is_none());
        assert_eq!(rag.default_payload["model_id"], serde_json::Value::Null);
    }
}
