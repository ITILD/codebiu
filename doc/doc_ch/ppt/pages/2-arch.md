---
glow: right
---

# 系统架构：前后端分离 + 模块化

## 请求链路

```mermaid {scale: 0.7}
graph TD
    A[浏览器 Vue3] -->|HTTP/JSON| B[Nginx/代理]
    B -->|/base_server/*| C[FastAPI 主应用]
    C --> D[module_authorization 认证]
    D --> E[module_file / module_rag / ...]
    E --> F[Service 业务层]
    F --> G[DAO 数据访问层]
    G --> H[(PostgreSQL)]

    F -.->|文件存储| I[本地 / rustfs(S3)]
```

## 后端模块划分

| 模块 | 职责 |
| :---: | :---: |
| `common` | 配置/日志/数据库/工具(公共层) |
| `module_main` | 字典、状态、数据概览 |
| `module_authorization` | 用户/角色/权限/Token |
| `module_file` | 虚拟文件系统(哈希去重) |
| `module_rag` | 知识库项目/文档/对话 |
| `module_ai` | LLM/OCR/语音/模型配置 |
| `module_template` | 新模块开发参考模板 |

<div class="note-tip">
每个模块以 <code>module_</code> 前缀隔离,各自挂载到主应用的子路径下,互不干扰 — 这是项目的核心设计思想。
</div>
