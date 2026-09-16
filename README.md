# codebiu

多平台快速开发部署基线项目：前后端分离 + 文档 + 运维一体化的项目模板，可作为新项目的起点复制扩展。

## 仓库结构

```
codebiu/
├── code/
│   ├── backend/
│   │   ├── server_py/    # 后端基线：Python 3.13 + FastAPI + SQLAlchemy 2.0(异步) + PostgreSQL
│   │   └── server_rs/    # Rust 后端基线
│   └── frontend/
│       ├── vue3/         # 主前端基线：Vue3 + TypeScript + Vite + Element Plus + UnoCSS + Pinia
│       └── react/        # React 前端基线
├── doc/doc_ch/           # 项目文档（中文）
└── deveops/              # 部署指南、运维脚本、运维手册（docker）
```

## 核心能力

- **权限**：Casbin 域分离 RBAC（全局菜单/按钮/接口）+ 项目级数据权限（成员/部门三档位）
- **AI**：LLM 工具链（流式对话、OCR、重排、语音 ASR/TTS）、RAG 知识库（向量检索 + 意图分析）、智能体、LLM 数据清洗、模型按用户/部门隔离（public/dept/user）
- **通用**：JWT 认证、文件系统（预签名 URL、去重、引用计数）、多数据库（PostgreSQL + LanceDB/Milvus + 图数据库）、任务调度（Celery + 本地双引擎）、websearch（Tavily/Firecrawl）
- **工程**：uv / pnpm 包管理，docker 开发部署，SQLite+Fakeredis+LanceDB 零依赖本地开发组合

## 快速开始

```bash
# 后端
cd code/backend/server_py
uv sync
cp config_template_full.yaml config.dev.yaml
python src/app.py            # http://127.0.0.1:2001/docs

# 前端
cd code/frontend/vue3
pnpm i
pnpm run dev                 # http://localhost:5173（代理 /base_server → 2001）
```

数据库 / docker 等环境安装详见 [开发环境配置](doc/doc_ch/01-入门/3-开发环境.md)。

## 文档导航

| 目录 | 内容 |
| :--- | :--- |
| [doc/doc_ch/](doc/doc_ch/README.md) | 文档总导航 |
| [01-入门](doc/doc_ch/01-入门/) | 技术基础、环境配置、IDE 插件 |
| [02-开发指南](doc/doc_ch/02-开发指南/) | 后端 / 前端开发、权限体系、大模型调用 |
| [03-设计文档](doc/doc_ch/03-设计文档/) | 需求分析、架构设计、权限设计 |
| [04-规范](doc/doc_ch/04-规范/) | 代码规范、开发流程、版本管理 |
| [05-初始开发](doc/doc_ch/05-初始开发/) | 0.x 基线搭建期记录 |
| [06-版本开发](doc/doc_ch/06-版本开发/) | v1.x 各版本功能与排期 |
| [deveops](deveops/README.md) | 部署指南与运维 |

## 版本概览

| 版本 | 周期 | 主题 |
| :--- | :--- | :--- |
| 0.x 初始开发 | 2025-11 ~ 2026-06 | 前后端基线、认证/文件/数据库/LLM 通用能力 |
| v1.0.0 | 2026-07 | RAG 知识库、Casbin 权限、语音模块 |
| v1.1.0 | 2026-08 | LLM 工具链重构、容器化运维 |
| v1.2.0 | 2026-09 上旬 | 智能体、LLM 数据清洗、地理可视化、模型分部门 |
| v1.3.0（开发中） | 2026-09 中旬 ~ | 双引擎任务调度、体验统一、权限 v4 |

## 贡献方式

分支 `dev` 开发，PR 审查后合入 `main`；遵循 [开发规范](doc/doc_ch/04-规范/代码规范.md) 与 [版本管理](doc/doc_ch/04-规范/版本管理.md)。
