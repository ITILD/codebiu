//! server_rs 主入口(对应 Python 侧 src/app.py)
//!
//! 启动流程: 日志初始化 → 配置加载 → 数据库连接 → 启动钩子(建表/种子/casbin)
//! → 路由挂载(/authorization 子应用 + module-main 根路由) → 监听

use axum::routing::get;
use axum::Router;
use common::runtime::AppState;
use common::config;

#[tokio::main]
async fn main() {
    // 日志初始化(RUST_LOG 优先, 默认 info)
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    // 配置加载(五层覆盖, 失败即启动终止)
    let config = match config::init() {
        Ok(cfg) => cfg,
        Err(e) => {
            eprintln!("配置加载失败: {e}");
            std::process::exit(1);
        }
    };
    tracing::info!(
        "启动 {} v{} (dev={}, port={})",
        config.global.name,
        config.global.version,
        config.state.is_dev,
        config.server.port
    );

    // 全局状态构建
    let state = match AppState::new(config).await {
        Ok(state) => state,
        Err(e) => {
            eprintln!("数据库连接失败: {e}");
            std::process::exit(1);
        }
    };
    tracing::info!("数据库连接成功: {}", config.db_rel.r#type);

    // 启动钩子(对齐 Python lifespan: 建表 → 各类种子/策略初始化, 单个失败仅告警不阻断)
    run_boot_hooks(&state).await;

    // 路由挂载(模块化, 对应 Python app.mount)
    let app = build_router(&state);

    // 监听
    let addr = format!("{}:{}", config.server.host, config.server.port);
    let listener = match tokio::net::TcpListener::bind(&addr).await {
        Ok(l) => l,
        Err(e) => {
            eprintln!("端口绑定失败 {addr}: {e}");
            std::process::exit(1);
        }
    };
    tracing::info!("服务已启动: http://{addr}");
    if let Err(e) = axum::serve(listener, app).await {
        eprintln!("服务运行异常: {e}");
        std::process::exit(1);
    }
}

/// 启动钩子: 权限声明注册 → 表注册 → 建表 → 动态配置种子 → casbin → 默认管理员 → 字典种子
///
/// 对齐 Python server_start 流程(runtime 装配 → 建表 → INIT_HOOKS);
/// 单个钩子失败仅记录告警, 不阻断后续钩子与启动。
async fn run_boot_hooks(state: &AppState) {
    // 1) 模块权限声明注册(sys + main + site + 各业务域, 对齐 Python 导入期 registry.register)
    module_authorization::register_permissions();
    module_main::register_permissions();
    module_site::register_permissions();
    // 生活模块: 宝宝起名(/life 域, 权限码 life/baby_name)
    module_life::register_permissions();
    // 基础模板 / 开发辅助 / 同义词(contact 仅服务库无端点, 不声明权限)
    module_template::register_permissions();
    module_dev_tools::register_permissions();
    module_nlp::register_permissions();
    // AI / 任务队列 / 知识库 / 智能体 / 几何 / 文档解析(对齐 Python 各模块权限声明)
    module_ai::register_permissions();
    module_task::register_permissions();
    module_rag::register_permissions();
    module_agent::register_permissions();
    module_geometry::register_permissions();
    module_office::register_permissions();

    // 2) 各模块表注册(实体分散在各模块 do/entity, 对齐 Python SQLModel.metadata 聚合)
    common::register_tables();
    module_authorization::register_tables();
    module_main::register_tables();
    module_site::register_tables();
    module_life::register_tables();
    module_template::register_tables();
    module_dev_tools::register_tables();
    module_nlp::register_tables();
    module_file::register_tables();
    // ai / task / rag / agent / geometry 模块表
    module_ai::register_tables();
    module_task::register_tables();
    module_rag::register_tables();
    module_agent::register_tables();
    module_geometry::register_tables();

    // 3) 全量建表(if_not_exists 幂等)
    match common::utils::tables::create_all(&state.db).await {
        Ok(_) => tracing::info!("Database tables init successfully."),
        Err(e) => tracing::error!("建表失败: {e}"),
    }

    // 4) 动态配置首启种子(yaml 同名节覆盖默认值建行, 幂等不覆盖已有行)
    if let Err(e) = state.settings.seed_from_yaml(config::raw_json()).await {
        tracing::warn!("动态配置种子初始化失败: {e}");
    }

    // 5) casbin enforcer 初始化(从 casbin_rule 表加载策略并同步权限声明)
    if !module_authorization::casbin_mgr::auth().init(state.db.clone()).await {
        tracing::warn!("Casbin enforcer 初始化失败");
    }

    // 6) 默认管理员引导(幂等创建/修复)
    module_authorization::bootstrap::ensure_default_admin(&state.db, &state.settings).await;

    // 7) 字典种子同步(幂等补缺)
    module_main::bootstrap::ensure_default_dicts(&state.db).await;

    // 8) 文件物理存储就绪检查(local 建目录 / s3 建桶+CORS, 对齐 Python INIT_HOOKS)
    module_file::utils::storage::ensure_ready(state).await;

    // 9) AI 模块钩子(default_models 首启种子写库, 对齐 Python INIT_HOOKS)
    module_ai::init_hooks(state).await;
    // 几何模块钩子(历史 PostGIS 库 geometry 列幂等迁移为 WKT 文本)
    module_geometry::init_hooks(state).await;

    // 10) RAG 模块钩子(文档解析/重向量化任务执行器注册 + 下载授权钩子)
    module_rag::init_task_runners(state.clone());
    module_rag::init_download_grant(state.clone());

    // 11) Agent 模块钩子(内置公共智能体种子)
    module_agent::init_hooks(state).await;

    // 12) 任务队列 worker 启动(本地引擎轮询执行, 放在执行器注册之后)
    module_task::start_worker(state.clone()).await;
}

/// 组装总路由(各模块 Router 在此挂载, 对应 Python app.mount 前缀)
fn build_router(state: &AppState) -> Router {
    let mut app = Router::new()
        .route("/status", get(status_handler))
        // 授权模块: 7 组路由统一挂 /authorization 子应用
        .nest("/authorization", module_authorization::router())
        // 基础资源模块: 字典/数据库/配置/状态/静态资源挂根路径
        .merge(module_main::router())
        // 个人小站模块: 博客/备忘/记账挂 /site 子应用
        .nest("/site", module_site::router())
        // 生活模块: 宝宝起名挂 /life 子应用
        .nest("/life", module_life::router())
        // 基础模板 / 开发辅助 / 同义词挂对应前缀子应用(与 Python app.mount 前缀一致;
        // contact 与 module-graph 均为服务库, Python 侧亦无端点, 不挂路由)
        .nest("/template", module_template::router())
        .nest("/dev-tools", module_dev_tools::router())
        .nest("/nlp", module_nlp::router())
        // 文件模块: 虚拟文件系统挂 /file 子应用
        .nest("/file", module_file::router())
        // 网页搜索模块: 多引擎搜索挂 /websearch 子应用
        .nest("/websearch", module_websearch::router())
        // AI 模块: 模型配置/LLM/OCR/语音/重排挂 /ai 子应用
        .nest("/ai", module_ai::router())
        // 任务队列模块挂 /task 子应用
        .nest("/task", module_task::router())
        // 知识库模块挂 /rag 子应用
        .nest("/rag", module_rag::router())
        // 智能体模块挂 /agent 子应用
        .nest("/agent", module_agent::router())
        // 地理空间模块挂 /geometry 子应用
        .nest("/geometry", module_geometry::router())
        // 文档解析模块挂 /office 子应用(对齐 Python config/server.py 声明前缀)
        .nest("/office", module_office::router())
        // 头像端点契约路径在 /authorization 下(实现位于 module-file, 见其 lib.rs 说明)
        .nest("/authorization", module_file::avatar_router())
        // 中间件(顺序: 日志/计时在最外层)
        .layer(axum::middleware::from_fn(
            common::utils::middleware::process_time_middleware,
        ));

    if config::get().middleware.cors {
        app = app.layer(common::utils::middleware::cors_layer());
    }
    if config::get().middleware.gzip {
        app = app.layer(common::utils::middleware::compression_layer());
    }

    app.with_state(state.clone())
}

/// 健康检查端点
async fn status_handler() -> &'static str {
    "ok"
}
