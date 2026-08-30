---
layout: two-cols
layoutClass: gap-8
glow: left
---

# 项目概览：codebiu 是什么

## 一句话介绍

一套**前后端分离的后台管理系统基线项目**，开箱即用地提供登录认证、权限管理、文件管理、知识库、AI 能力等通用功能。

## 仓库结构

```
codebiu/
├── code/
│   ├── backend/
│   │   └── server_py/    # 后端 FastAPI
│   └── frontend/
│       ├── vue3/         # 主前端(Vue3)
│       └── react/        # 备选前端(Next.js)
├── doc/
│   └── doc_ch/           # 开发文档(本PPT在此)
├── deveops/              # 部署运维文档
└── template_source/      # 参考模板(勿直接修改)
```

::right::

## 核心技术栈

| 层 | 技术 |
| :---: | :---: |
| 后端框架 | FastAPI (Python 3.13) |
| ORM | SQLAlchemy 2.0 (异步) |
| 数据库 | PostgreSQL (+ pgvector) |
| 权限 | Casbin (RBAC) |
| 前端框架 | Vue3 + TypeScript |
| UI 库 | Element Plus |
| 原子化样式 | UnoCSS |
| 包管理 | uv / pnpm |

<div class="note-tip">
后端 Python 全部使用 <b>3.13 新语法</b>：如 <code>str | None</code> 联合类型，不用 <code>typing.Optional</code>。
</div>
