//! 任务队列 Worker 独立入口(对应 Python 侧 src/app_task.py, 消费框架由 Celery 换为 Apalis)
//!
//! 启动流程对齐 Python app_task: 幂等建表 → casbin 只读初始化(执行时以任务创建者身份复检)
//! → 启动自愈重派遗留任务 → 进入消费循环(Apalis Redis 队列 task_queue, 单 worker 串行消费,
//! 对齐 celery --pool=solo --concurrency=1)。
//!
//! 任务消息仅携带 task_id(极简原则): payload/user_id 由执行侧从 task_queue 表读取,
//! 重复消费由 run_local_task 的原子认领(pending → running)挡住, 与 API 进程 local 引擎
//! 共用同一执行主体, 双进程混跑安全。

use apalis::prelude::{Data, Error, WorkerFactoryFn};
use common::config;
use common::config::dynamic::TasksSettings;
use common::runtime::AppState;
use module_task::TaskJob;

#[tokio::main]
async fn main() {
    // 日志初始化(RUST_LOG 优先, 默认 info)
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    // 配置加载 + 全局状态构建(与 API 进程同一套初始化)
    let config = match config::init() {
        Ok(cfg) => cfg,
        Err(e) => {
            eprintln!("配置加载失败: {e}");
            std::process::exit(1);
        }
    };
    let state = match AppState::new(config).await {
        Ok(state) => state,
        Err(e) => {
            eprintln!("数据库连接失败: {e}");
            std::process::exit(1);
        }
    };
    tracing::info!("任务 Worker 数据库连接成功: {}", config.db_rel.r#type);

    // 1) 幂等建表(对齐 Python _ensure_task_table): 权限声明 + 表注册 + create_all + 动态配置种子
    register_and_create_tables(&state).await;

    // 2) casbin enforcer 只读初始化(对齐 Python init_worker_authorization:
    //    worker 不挂路由, 仅加载策略供执行器以任务创建者身份复检权限)
    if !module_authorization::casbin_mgr::auth().init(state.db.clone()).await {
        tracing::warn!("Casbin enforcer 初始化失败(权限复检将拒绝)");
    }

    // 3) 任务执行器注册(demo 内置自动注册 + RAG 文档解析/重向量化)
    module_rag::init_task_runners(state.clone());

    // 4) 读取任务引擎配置(建表/种子之后读取, 首启才有 tasks 行)
    let settings: TasksSettings = match state.settings.get("tasks").await {
        Ok(s) => s,
        Err(e) => {
            eprintln!("读取任务引擎配置失败: {e}");
            std::process::exit(1);
        }
    };
    if settings.engine != "celery" {
        tracing::warn!(
            "当前任务引擎为 {}(非 celery), 队列暂无生产者; Worker 继续待命, 切换引擎后即时生效",
            settings.engine
        );
    }
    if settings.broker_url.is_empty() || settings.broker_url == "memory://" {
        eprintln!("celery 引擎未配置 Redis broker(tasks.broker_url), 无法启动 Worker");
        std::process::exit(1);
    }

    // 5) 启动自愈: 重派"创建超过 60s 仍 pending"的遗留任务(对齐 Python recover_pending_tasks)
    let recovered = module_task::recover_pending_tasks(&state).await;
    tracing::info!("启动自愈完成, 重派遗留任务 {recovered} 个");

    // 6) 进入 Apalis 消费循环(单 worker 串行, 对齐 celery --pool=solo --concurrency=1)
    let node = format!(
        "task_worker@{}#{}",
        std::env::var("HOSTNAME").unwrap_or_else(|_| "localhost".to_string()),
        std::process::id()
    );
    let conn = match apalis_redis::connect(settings.broker_url.as_str()).await {
        Ok(c) => c,
        Err(e) => {
            eprintln!("Redis 连接失败({}): {e}", settings.broker_url);
            std::process::exit(1);
        }
    };
    let queue_config = apalis_redis::Config::default().set_namespace("task_queue");
    let storage = apalis_redis::RedisStorage::new_with_config(conn, queue_config);
    tracing::info!("任务 Worker {node} 启动, 消费队列 task_queue (broker: {})", settings.broker_url);
    // run() 正常情况下随进程退出返回; 到达此处视为消费循环已结束
    apalis::prelude::WorkerBuilder::new(node)
        .data(state)
        .backend(storage)
        .build_fn(execute_task)
        .run()
        .await;
    tracing::warn!("任务 Worker 消费循环已退出");
}

/// 幂等建表: 权限声明注册 → 表注册 → create_all → 动态配置种子
///
/// 对齐 Python _ensure_task_table 的幂等语义; 注册清单与 API 进程 main.rs 保持一致
/// (实体分散在各模块, 缺注册会导致建表缺表)。
async fn register_and_create_tables(state: &AppState) {
    // 模块权限声明注册(与 main.rs 一致, casbin 复检依赖权限声明元数据)
    module_authorization::register_permissions();
    module_main::register_permissions();
    module_site::register_permissions();
    module_life::register_permissions();
    module_template::register_permissions();
    module_dev_tools::register_permissions();
    module_nlp::register_permissions();
    module_ai::register_permissions();
    module_task::register_permissions();
    module_rag::register_permissions();
    module_agent::register_permissions();
    module_geometry::register_permissions();
    module_office::register_permissions();

    // 各模块表注册(与 main.rs 一致)
    common::register_tables();
    module_authorization::register_tables();
    module_main::register_tables();
    module_site::register_tables();
    module_life::register_tables();
    module_template::register_tables();
    module_dev_tools::register_tables();
    module_nlp::register_tables();
    module_file::register_tables();
    module_ai::register_tables();
    module_task::register_tables();
    module_rag::register_tables();
    module_agent::register_tables();
    module_geometry::register_tables();

    // 全量建表(if_not_exists 幂等)
    if let Err(e) = common::utils::tables::create_all(&state.db).await {
        tracing::error!("建表失败: {e}");
    }

    // 动态配置首启种子(幂等不覆盖已有行; Worker 需读取 tasks 节配置)
    if let Err(e) = state
        .settings
        .seed_from_yaml(config::raw_json())
        .await
    {
        tracing::warn!("动态配置种子初始化失败: {e}");
    }
}

/// 任务消费处理器: 消息仅携带 task_id, 执行主体与 local 引擎共用 run_local_task
///
/// 原子认领(pending → running)天然防止与 API 进程/其它 Worker 重复消费;
/// 业务失败已由 run_local_task 回写终态, 此处恒返回 Ok(避免 Apalis 对失败消息重试造成双跑)。
async fn execute_task(job: TaskJob, data: Data<AppState>) -> Result<(), Error> {
    let task_id = job.task_id.clone();
    tracing::info!("Worker 认领任务: {task_id}");
    module_task::run_local_task(data.db.clone(), task_id).await;
    Ok(())
}
