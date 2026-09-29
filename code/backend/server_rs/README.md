# server_rs

项目后端基线库（Rust 版，与 Python 侧 `server_py` 同构）

## 技术栈

- 运行时/Web 框架：tokio + axum（对应 Python asyncio + FastAPI）
- ORM：sea-orm（sqlite / postgres，对应 SQLModel）
- 权限引擎：casbin（域 RBAC，`rbac_model.conf`，策略持久化 `casbin_rule` 表）
- 任务队列：apalis + Redis（对应 Celery，worker 独立二进制 `app_task`）

## 项目结构

```text
server_rs
├── Cargo.toml            # workspace 清单(版本/公共依赖集中管理)
├── config.yaml           # 配置基线层(入 git)
├── config.seed.yaml      # 约定种子层(gitignored, 存在即加载)
├── config.dev.yaml       # 环境覆盖层(gitignored, .env 写 APP_ENV=dev 加载)
├── .env                  # 环境声明(gitignored): APP_ENV
├── rbac_model.conf       # casbin 模型
├── public/               # 静态资源
├── temp_source/          # 运行期数据(上传/日志/db, gitignored)
├── crates
│   ├── app               # 入口: server_rs(主服务) + app_task(任务 worker)
│   ├── common            # 公共包: 配置/运行时/中间件/工具
│   ├── module-authorization  # 授权: 挂 /authorization
│   ├── module-main          # 基础资源(字典/配置/状态): 挂根路径
│   ├── module-site          # 个人小站(博客/备忘/记账): 挂 /site
│   ├── module-life          # 生活(宝宝起名): 挂 /life
│   ├── module-template      # 基础模板: 挂 /template
│   ├── module-dev-tools     # 开发辅助: 挂 /dev-tools
│   ├── module-nlp           # NLP: 挂 /nlp
│   ├── module-contact       # 联系人/同义词(服务库, 无端点)
│   ├── module-graph         # 图服务(服务库, 无端点)
│   ├── module-file          # 文件虚拟系统: 挂 /file
│   ├── module-websearch     # 网页搜索: 挂 /websearch
│   ├── module-ai            # AI(模型配置/LLM/OCR/语音/重排): 挂 /ai
│   ├── module-task          # 任务队列: 挂 /task
│   ├── module-rag           # 知识库: 挂 /rag
│   ├── module-agent         # 智能体: 挂 /agent
│   ├── module-geometry      # 地理空间: 挂 /geometry
│   └── module-office        # 文档解析(MinerU): 挂 /office
└── tools/docker_dev      # Dockerfile.dev + build.sh
```

## 开发

```bash
# 版本和三方库在 Cargo.toml 里，安装依赖
cargo fetch

# 运行(默认 0.0.0.0:2001)
cargo run --bin server_rs

# 任务队列 worker(独立进程, 需要 Redis)
cargo run --bin app_task

# 检查/测试
cargo clippy
cargo test
```

## 配置分层(低 → 高，后层覆盖前层)

1. `config.yaml` 基线层(入 git，必需)
2. `config.seed.yaml` 约定种子层(gitignored，存在即加载)
3. `APP_ENV` 环境覆盖层：`.env` 写 `APP_ENV=dev` → 加载 `config.dev.yaml`
4. `CONFIG_PATH` 部署覆盖层(逗号分隔多文件按序覆盖)
5. `CODEBIU_*` 环境变量键级覆盖(嵌套键双下划线)：`CODEBIU_SERVER__PORT=3000`

默认管理员：`admin / admin123`（`admin.reset_password` 置 true 可重置）

## 打包 docker

```sh
# dev(构建镜像 server_rs:<Cargo.toml 版本号>)
bash tools/docker_dev/build.sh

# 或从运维脚本目录构建
bash deveops/运维脚本/docker_dev/build_docker_server_rs.sh

# 运行
docker compose up
docker compose down
```

## 启动流程

日志初始化 → 配置加载 → 数据库连接 → 启动钩子(建表/种子/casbin/管理员/字典/存储就绪/worker)
→ 路由挂载(各模块子应用) → 监听

## 项目文档

- [版本信息](../../doc/doc_ch/01-入门/2-项目基础.md)
