# Min服务模板

一个极简的全栈Web服务模板，包含后端API、前端界面和数据库集成，适合快速原型开发和学习使用。

## 特性

- **后端**: 使用 FastAPI 框架提供高性能的异步API
- **数据库**: 使用 SQLModel (SQLAlchemy + Pydantic) 进行ORM操作
- **前端**: Vue 3 驱动的单页应用，提供用户友好的界面
- **数据库**: SQLite 作为轻量级本地数据库
- **API文档**: 自动化的 Swagger UI 接口文档

## 技术栈

- Python 3.11+
- FastAPI
- SQLModel
- SQLite + aiosqlite
- Vue 3
- Uvicorn ASGI服务器

## 功能

- 用户管理 CRUD 操作 (创建、读取、更新、删除)
- 前端用户界面，可直接添加、编辑、删除用户
- API 接口自动验证和错误处理
- 响应式设计，适配不同屏幕尺寸

## 快速开始

### 环境要求

- Python 3.11 或更高版本
- uv 包管理器

### 安装与运行

1. 克隆项目到本地

2. 安装依赖：
   ```bash
   # 如果使用 uv (推荐)
   uv sync
   ```

3. 启动服务：

   ```sh
   # vscode debug模式启动
   # dev启动服务
   .venv\Scripts\python.exe main.py
   ```

4. 访问以下地址：
   - 应用主页: http://localhost:3100
   - API 文档: http://localhost:3100/docs
   - ReDoc 文档: http://localhost:3100/redoc

## 项目结构

```
server_min_py/
├── main.py                 # 主应用文件，包含FastAPI应用和CRUD路由
├── pyproject.toml          # 项目依赖配置文件
├── source/                 # 静态资源目录
│   ├── main/               # 主应用前端资源
│   │   ├── index.html      # 主页面
│   │   └── assets/         # 前端静态资源
│   └── common/             # 公共资源
│       └── assets/         # 公共静态资源
├── temp_source/                   # 临时文件目录（包括数据库）
│   └── template.db         # SQLite数据库文件
└── README.md               # 项目说明文档
```

## API 接口

- `GET /` - 返回主页
- `POST /users/` - 创建新用户
- `GET /users/` - 获取所有用户
- `GET /users/{user_id}` - 根据ID获取特定用户
- `PUT /users/{user_id}` - 更新用户信息
- `DELETE /users/{user_id}` - 删除用户

## 使用场景

此模板适用于：

- 快速原型开发
- 学习 FastAPI 和 SQLModel
- 构建小型Web应用
- 教学演示
- 个人项目的基础框架


## 配置

如果需要修改服务器配置，可以在 `main.py` 中调整以下变量：

- `HOST`: 服务器主机地址 (默认: "0.0.0.0")
- `PORT`: 服务器端口 (默认: 3100)
- `database_url`: 数据库连接URL (默认: SQLite数据库)

## 注意事项

- 数据库存储在 `temp_source/template.db` 文件中
- 每次重启应用时会重新创建数据库表
- 仅适用于开发和测试环境，生产环境请使用更安全的数据库解决方案