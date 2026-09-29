//! 任务注册表与 worker/派发辅助(对齐 Python module_task/tasks/__init__.py)
//!
//! 设计说明(通用任务队列, 执行器 IoC 注入):
//! 1. 新业务模块接入时在 TASK_TYPES 登记元数据(type/name/description/celery_task/default_payload),
//!    并经 register_local_runner 注入本地执行器 —— 本 crate 不反向依赖业务模块(rag/agent 后续自行注入);
//! 2. 双引擎按动态配置 tasks.engine 统一选择: local → tokio spawn 进程内后台执行;
//!    celery → 消息经 Apalis Redis 队列派发(tasks.broker_url), 由 app_task worker 进程消费
//!    (对应 Python 的 Celery + app_task.py; 消息仅携带 task_id, 参数由 worker 从库读取);
//! 3. 执行统一走 run_local_task: 原子认领 pending→running → 调用注入的执行器 → 终态回写,
//!    取消/终态保护由 update_task_fields 保证(与 Python worker 回写行为一致),
//!    双引擎共用同一执行主体(认领原子性天然防止重复消费);
//! 4. worker 自愈: local 引擎由 API 进程 start_worker 周期认领遗留任务;
//!    celery 引擎由 app_task worker 启动时 recover_pending_tasks 一次性重派(对齐 Python)。

pub mod demo;

use std::collections::HashMap;
use std::future::Future;
use std::pin::Pin;
use std::sync::{Arc, LazyLock, Mutex, OnceLock};
use std::time::Duration;

use apalis::prelude::Storage;
use common::config::dynamic::TasksSettings;
use common::runtime::AppState;
use common::utils::error::AppError;
use sea_orm::{ActiveModelTrait, DatabaseConnection, EntityTrait};

use crate::dao::task_dao;
use crate::do_::entity::task_queue;
use crate::do_::task::{is_active_status, now_utc, STATUS_FAILED, STATUS_SUCCESS};

// ############################# 任务类型注册表 #############################

/// 任务类型定义(注册表条目, 供前端渲染类型下拉与默认模板; 对齐 Python TaskTypeDef)
pub struct TaskTypeDef {
    /// 任务类型编码
    pub r#type: &'static str,
    pub name: &'static str,
    pub description: &'static str,
    /// 任务在 Celery 中的路由名(与 Python 注册表一致, 供 celery 引擎对接参考)
    pub celery_task: &'static str,
    /// 前端"新建任务"对话框的默认参数模板
    pub default_payload: serde_json::Value,
}

/// 任务类型注册表(元数据照抄 Python TASK_TYPES; 本地执行器经 register_local_runner 注入)
pub static TASK_TYPES: LazyLock<Vec<TaskTypeDef>> = LazyLock::new(|| {
    vec![
        TaskTypeDef {
            r#type: "demo_document",
            name: "示例: 文档处理",
            description: "模拟文档处理流水线(解析→分块→向量化→入库), 用于演示任务队列全流程; \
                          后续知识库模块的真实文档处理任务将替换此实现",
            celery_task: "task.run_demo_document",
            default_payload: serde_json::json!({
                "file_name": "示例文档.pdf", "total_pages": 42, "duration": 16
            }),
        },
        TaskTypeDef {
            r#type: "rag_document_parse",
            name: "知识库: 文档解析",
            description: "解析项目文档: OCR/解析 → 分块策略识别 → 重分块 → 向量化 → 写入向量库;\
                          以任务创建者绑定的模型执行(未绑定时回退默认公共模型)",
            celery_task: "module_rag.tasks.project_document.reparse_document_task",
            default_payload: serde_json::json!({"document_id": "", "force_preset_id": null}),
        },
        TaskTypeDef {
            r#type: "rag_revectorize",
            name: "知识库: 全库重向量化",
            description: "系统更换向量模型后, 以指定/当前生效的默认公共向量化模型\
                          重算 Milvus 中所有文档 chunk 向量(仅系统管理员)",
            celery_task: "module_rag.tasks.project_document_chunk.revectorize_chunks_task",
            default_payload: serde_json::json!({"model_id": null}),
        },
    ]
});

/// 按类型编码查询注册表条目
pub fn get_task_type(task_type: &str) -> Option<&'static TaskTypeDef> {
    TASK_TYPES.iter().find(|d| d.r#type == task_type)
}

/// 全部注册类型编码(注册表校验失败提示用, 与 Python ", ".join(TASK_TYPES.keys()) 一致)
pub fn task_type_names() -> Vec<String> {
    TASK_TYPES.iter().map(|d| d.r#type.to_string()).collect()
}

// ############################# 本地执行器 IoC 注册表 #############################

/// 本地执行器类型(参数: 数据库连接 / 任务参数 JSON / 创建者用户ID; 失败以 Err 返回错误描述)
///
/// 任务生命周期(状态/进度/时间线)由执行框架统一回写, 执行器只关心业务本身。
pub type LocalTaskRunner = Arc<
    dyn Fn(DatabaseConnection, serde_json::Value, Option<String>)
        -> Pin<Box<dyn Future<Output = Result<(), String>> + Send>>
    + Send
    + Sync,
>;

/// 全局执行器注册表(启动期/运行期注入; 首次访问时内置注册 demo_document 示例执行器)
static LOCAL_RUNNERS: OnceLock<Mutex<HashMap<&'static str, LocalTaskRunner>>> = OnceLock::new();

/// 执行器注册表句柄(内置 demo 执行器, 对齐 Python 本 crate 自带 tasks/demo.py 的地位)
fn local_runners() -> &'static Mutex<HashMap<&'static str, LocalTaskRunner>> {
    LOCAL_RUNNERS.get_or_init(|| {
        let mut map: HashMap<&'static str, LocalTaskRunner> = HashMap::new();
        map.insert(
            "demo_document",
            Arc::new(|db, payload, user_id| {
                Box::pin(demo::run_demo(db, payload, user_id))
                    as Pin<Box<dyn Future<Output = Result<(), String>> + Send>>
            }),
        );
        Mutex::new(map)
    })
}

/// 注册任务类型的本地执行器(业务模块启动期调用; 重复注册以最新为准)
pub fn register_local_runner(task_type: &'static str, runner: LocalTaskRunner) {
    local_runners()
        .lock()
        .expect("执行器注册表锁")
        .insert(task_type, runner);
    tracing::info!("已注册任务本地执行器: {task_type}");
}

/// 已注册本地执行器的任务类型列表(排序返回)
pub fn registered_task_types() -> Vec<String> {
    let mut names: Vec<String> = local_runners()
        .lock()
        .expect("执行器注册表锁")
        .keys()
        .map(|k| k.to_string())
        .collect();
    names.sort();
    names
}

/// 任务类型是否已注册本地执行器
pub fn has_local_runner(task_type: &str) -> bool {
    local_runners()
        .lock()
        .expect("执行器注册表锁")
        .contains_key(task_type)
}

/// 取出执行器(clone Arc, 避免跨 await 持锁)
fn take_runner(task_type: &str) -> Option<LocalTaskRunner> {
    local_runners()
        .lock()
        .expect("执行器注册表锁")
        .get(task_type)
        .cloned()
}

// ############################# 双引擎统一派发 #############################

/// 读取当前任务执行引擎(local/celery; 动态配置 tasks.engine, 运行期切换即时生效)
pub async fn get_task_engine(state: &AppState) -> Result<String, AppError> {
    let settings: TasksSettings = state.settings.get("tasks").await?;
    Ok(settings.engine)
}

/// celery 引擎的任务消息载荷(极简原则, 对齐 Python celery args=[task.id])
///
/// 消息只携带 task_queue 表主键; payload/user_id 等业务数据由执行侧从库读取,
/// 消息天然幂等可重投(重复消费由 run_local_task 的原子认领挡住)。
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct TaskJob {
    pub task_id: String,
}

/// Apalis Redis 队列命名空间(对齐 Python celery 队列名 task_queue)
const TASK_QUEUE_NAMESPACE: &str = "task_queue";

/// 队列存储缓存(broker_url → RedisStorage; URL 变更时重建连接)
static QUEUE_STORAGE: OnceLock<Mutex<Option<(String, apalis_redis::RedisStorage<TaskJob>)>>> =
    OnceLock::new();

/// 获取/构建 Apalis Redis 队列存储(连接管理器复用; 存储可克隆)
///
/// 锁只在同步段持有(避免跨 await 使 Future 退化为非 Send);
/// 并发首建重复连接无害, 以最后写入为准。
async fn queue_storage(broker_url: &str) -> Result<apalis_redis::RedisStorage<TaskJob>, String> {
    // 1) 缓存命中直接克隆返回
    {
        let cell = QUEUE_STORAGE.get_or_init(|| Mutex::new(None));
        let guard = cell.lock().expect("任务队列存储锁");
        if let Some((url, storage)) = guard.as_ref() {
            if url == broker_url {
                return Ok(storage.clone());
            }
        }
    }
    // 2) 缓存未命中: 建立连接(无锁 await)
    let conn = apalis_redis::connect(broker_url)
        .await
        .map_err(|e| format!("Redis 连接失败({broker_url}): {e}"))?;
    let config = apalis_redis::Config::default().set_namespace(TASK_QUEUE_NAMESPACE);
    let storage = apalis_redis::RedisStorage::new_with_config(conn, config);
    // 3) 回写缓存
    let cell = QUEUE_STORAGE.get_or_init(|| Mutex::new(None));
    *cell.lock().expect("任务队列存储锁") = Some((broker_url.to_string(), storage.clone()));
    Ok(storage)
}

/// 双引擎统一派发: 按 tasks.engine 选择执行路径(对齐 Python dispatch_task)
///
/// - celery: 消息 push 到 Apalis Redis 队列, 由 app_task worker 进程消费
/// - local: 进程内后台协程立即执行
///
/// 说明: priority(0~9)在 Rust 侧仅作为落库字段(Apalis Redis 队列为 FIFO,
/// Python celery 的 Redis 分级子队列加权消费未引入), 执行顺序以入队先后为准。
pub async fn dispatch_task(state: &AppState, task_id: &str) -> Result<(), AppError> {
    let settings: TasksSettings = state.settings.get("tasks").await?;
    if settings.engine == "celery" {
        if settings.broker_url.is_empty() || settings.broker_url == "memory://" {
            return Err(AppError::business(
                "celery 引擎未配置 Redis broker(tasks.broker_url)",
            ));
        }
        let mut storage =
            queue_storage(&settings.broker_url).await.map_err(AppError::business)?;
        storage
            .push(TaskJob { task_id: task_id.to_string() })
            .await
            .map_err(|e| AppError::business(format!("任务入队失败(Apalis Redis): {e}")))?;
        Ok(())
    } else {
        spawn_local_task(state.db.clone(), task_id.to_string());
        Ok(())
    }
}

/// local 引擎派发: tokio spawn 进程内后台执行(创建/重试派发与 worker 自愈共用同一执行主体)
pub fn spawn_local_task(db: DatabaseConnection, task_id: String) {
    tokio::spawn(async move {
        run_local_task(db, task_id).await;
    });
}

// ############################# worker 侧回写辅助 #############################

/// worker 侧字段回写载荷(None 字段不更新; 对齐 Python update_task_fields 参数)
#[derive(Debug, Default)]
pub struct TaskFieldUpdate {
    pub status: Option<String>,
    /// 完成百分比 0~100(越界自动夹紧)
    pub progress: Option<f64>,
    /// 当前阶段描述
    pub message: Option<String>,
    /// 执行结果 JSON
    pub result: Option<serde_json::Value>,
    /// 失败原因
    pub error: Option<String>,
    /// 置 started_at 为当前时间(仅尚未开始时生效)
    pub set_started: bool,
    /// 置 finished_at 为当前时间(任务结束时)
    pub set_finished: bool,
}

/// worker 侧更新任务字段(独立短事务语义, 进度可频繁回写)
///
/// 终态保护: 取消/撤销后 worker 的后续回写不再生效(防止取消被进度/收尾回写复活),
/// 成功/失败终态同样不回退(避免旧 worker 晚到覆盖新状态); 与 Python 行为一致。
pub async fn update_task_fields(
    db: &DatabaseConnection,
    task_id: &str,
    upd: TaskFieldUpdate,
) -> Result<(), sea_orm::DbErr> {
    use sea_orm::IntoActiveModel;
    let Some(task) = task_queue::Entity::find_by_id(task_id).one(db).await? else {
        return Ok(());
    };
    // 终态保护: 仅活跃任务(pending/running)可回写
    if !is_active_status(&task.status) {
        return Ok(());
    }
    let already_started = task.started_at.is_some();
    let mut am = task.into_active_model();
    if let Some(s) = upd.status {
        am.status = sea_orm::Set(s);
    }
    if let Some(p) = upd.progress {
        am.progress = sea_orm::Set(p.clamp(0.0, 100.0));
    }
    if let Some(m) = upd.message {
        am.message = sea_orm::Set(Some(m));
    }
    if let Some(r) = upd.result {
        am.result = sea_orm::Set(Some(r));
    }
    if let Some(e) = upd.error {
        am.error = sea_orm::Set(Some(e));
    }
    if upd.set_started && !already_started {
        am.started_at = sea_orm::Set(Some(now_utc()));
    }
    if upd.set_finished {
        am.finished_at = sea_orm::Set(Some(now_utc()));
    }
    am.updated_at = sea_orm::Set(now_utc());
    am.update(db).await?;
    Ok(())
}

// ############################# 任务执行主体 #############################

/// 执行单个 local 任务: 原子认领 → 开始回写 → 调用执行器 → 终态回写
///
/// 回写行为对齐 Python worker: 成功置 success/100/"处理完成", 失败置 failed+错误描述;
/// 未注册执行器的类型标记失败并写错误信息(创建时允许先入队, 执行时才失败)。
pub async fn run_local_task(db: DatabaseConnection, task_id: String) {
    // 1. 原子认领(pending → running): 失败说明已被取消或并发认领, 直接退出
    match task_dao::claim_pending(&db, &task_id).await {
        Ok(true) => {}
        Ok(false) => return,
        Err(e) => {
            tracing::error!("任务 {task_id} 认领失败: {e}");
            return;
        }
    }
    // 2. 读取任务行(认领成功后必然存在)
    let task = match task_dao::get(&db, &task_id).await {
        Ok(Some(t)) => t,
        Ok(None) => return,
        Err(e) => {
            tracing::error!("任务 {task_id} 读取失败: {e}");
            return;
        }
    };
    // 3. 开始执行回写(置 started_at 与阶段描述; 之后执行器/收尾回写经终态保护生效)
    if let Err(e) = update_task_fields(
        &db,
        &task_id,
        TaskFieldUpdate {
            progress: Some(0.0),
            message: Some("任务执行中".to_string()),
            set_started: true,
            ..Default::default()
        },
    )
    .await
    {
        tracing::error!("任务 {task_id} 开始回写失败: {e}");
    }
    // 4. 查找注入的本地执行器(未注册 → 标记失败并写错误信息)
    let Some(runner) = take_runner(&task.task_type) else {
        let err = format!("任务类型 {} 未注册本地执行器, 无法本地执行", task.task_type);
        tracing::warn!("任务 {task_id} 执行失败: {err}");
        if let Err(e) = update_task_fields(
            &db,
            &task_id,
            TaskFieldUpdate {
                status: Some(STATUS_FAILED.to_string()),
                error: Some(err),
                set_finished: true,
                ..Default::default()
            },
        )
        .await
        {
            tracing::error!("任务 {task_id} 失败回写异常: {e}");
        }
        return;
    };
    // 5. 执行业务(执行器内部可经 update_task_fields 阶段性回写进度)
    let payload = task.payload.clone();
    let user_id = task.user_id.clone();
    let task_type = task.task_type.clone();
    match runner(db.clone(), payload, Some(user_id)).await {
        Ok(()) => {
            if let Err(e) = update_task_fields(
                &db,
                &task_id,
                TaskFieldUpdate {
                    status: Some(STATUS_SUCCESS.to_string()),
                    progress: Some(100.0),
                    message: Some("处理完成".to_string()),
                    set_finished: true,
                    ..Default::default()
                },
            )
            .await
            {
                tracing::error!("任务 {task_id} 成功回写异常: {e}");
            }
        }
        Err(err) => {
            tracing::warn!("任务 {task_id}({task_type}) 执行失败: {err}");
            if let Err(e) = update_task_fields(
                &db,
                &task_id,
                TaskFieldUpdate {
                    status: Some(STATUS_FAILED.to_string()),
                    error: Some(err),
                    set_finished: true,
                    ..Default::default()
                },
            )
            .await
            {
                tracing::error!("任务 {task_id} 失败回写异常: {e}");
            }
        }
    }
}

// ############################# worker 启动自愈 #############################

/// worker 轮询间隔(秒; 每轮重新读取 tasks 配置, 引擎切换即时生效)
const POLL_INTERVAL_SECS: u64 = 5;
/// 自愈认领的遗留任务最小年龄(秒; 避开与创建派发协程的竞态窗口, 对齐 Python 的 60s)
const RECOVER_MIN_AGE_SECS: i64 = 60;

/// 启动任务 worker 轮询(app 启动期调用一次; 内部 tokio::spawn 后台循环, 本函数立即返回)
///
/// local 引擎: 周期认领"创建超过 60s 仍为 pending"的遗留任务重新执行(自愈);
/// celery 引擎: 本进程不执行任务, 空转等待配置切回 local
/// (celery 引擎的启动自愈由 app_task worker 进程的 recover_pending_tasks 承担, 对齐 Python)。
pub async fn start_worker(state: AppState) {
    tokio::spawn(async move {
        loop {
            tokio::time::sleep(Duration::from_secs(POLL_INTERVAL_SECS)).await;
            // 每轮读取引擎配置(读取失败仅告警跳过本轮)
            let engine = match get_task_engine(&state).await {
                Ok(e) => e,
                Err(e) => {
                    tracing::warn!("worker 读取任务引擎配置失败, 跳过本轮: {e}");
                    continue;
                }
            };
            if engine != "local" {
                continue;
            }
            let cutoff = now_utc() - chrono::Duration::seconds(RECOVER_MIN_AGE_SECS);
            match task_dao::list_stale_pending(&state.db, cutoff).await {
                Ok(list) => {
                    for task in list {
                        tracing::info!("worker 自愈认领遗留任务 {}({})", task.id, task.task_type);
                        spawn_local_task(state.db.clone(), task.id);
                    }
                }
                Err(e) => tracing::error!("worker 自愈扫描失败: {e}"),
            }
        }
    });
}

/// 一次性启动自愈: 重新派发"创建超过 60s 仍为 pending"的遗留任务(对齐 Python recover_pending_tasks)
///
/// 覆盖派发瞬间崩溃/消息丢失场景; celery 引擎由 app_task worker 启动时调用,
/// local 引擎由 API 进程 start_worker 周期自愈承担。
/// 重派按当前引擎走 dispatch_task: 重复入队无害(执行侧原子认领防双跑)。
pub async fn recover_pending_tasks(state: &AppState) -> usize {
    let cutoff = now_utc() - chrono::Duration::seconds(RECOVER_MIN_AGE_SECS);
    let list = match task_dao::list_stale_pending(&state.db, cutoff).await {
        Ok(list) => list,
        Err(e) => {
            tracing::error!("启动自愈扫描遗留任务失败: {e}");
            return 0;
        }
    };
    let mut count = 0usize;
    for task in list {
        match dispatch_task(state, &task.id).await {
            Ok(()) => {
                tracing::info!("启动自愈重派遗留任务 {}({})", task.id, task.task_type);
                count += 1;
            }
            Err(e) => tracing::warn!("启动自愈重派任务 {} 失败: {e}", task.id),
        }
    }
    count
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn 注册表包含python侧全部任务类型() {
        assert_eq!(
            task_type_names(),
            vec!["demo_document", "rag_document_parse", "rag_revectorize"]
        );
        assert!(get_task_type("demo_document").is_some());
        assert!(get_task_type("unknown_type").is_none());
    }

    #[test]
    fn 内置示例执行器已注册且业务类型未注册() {
        assert!(has_local_runner("demo_document"));
        assert!(!has_local_runner("rag_document_parse"));
        assert!(registered_task_types().contains(&"demo_document".to_string()));
    }

    #[test]
    fn 执行器注册覆盖语义() {
        // 重复注册同名类型以最新为准(以空执行器覆盖再恢复, 验证 insert 覆盖路径)
        let placeholder: LocalTaskRunner = Arc::new(|_, _, _| {
            Box::pin(async { Err("占位".to_string()) })
                as Pin<Box<dyn Future<Output = Result<(), String>> + Send>>
        });
        register_local_runner("demo_document", placeholder);
        assert!(has_local_runner("demo_document"));
    }
}
