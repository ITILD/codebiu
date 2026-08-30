---
layout: two-cols
layoutClass: gap-8
---

# 环境搭建：三步跑起来

## 1. 后端启动

```bash
cd code/backend/server_py
uv sync                # 安装 Python 3.13 + 依赖
# 复制 config.yaml 为 config.dev.yaml(数据库按需修改)
.venv\Scripts\python.exe src\app.py
```

启动后访问：`http://127.0.0.1:2001/template/docs`

## 2. 前端启动

```bash
cd code/frontend/vue3
pnpm i                 # 安装依赖
pnpm run dev           # 启动开发服务器
```

::right::

## 3. 数据库准备

```bash
# PostgreSQL 建库(以 pgvector 镜像为例)
docker run -d --name pg \
  -e POSTGRES_PASSWORD=yourpass \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```

- 用 Navicat 等工具连接
- 首次启动后端会**自动建表**

## 环境清单

| 工具 | 用途 |
| :---: | :---: |
| uv | Python 版本+依赖管理 |
| fnm + pnpm | Node 版本+包管理 |
| VSCode | IDE(装 Python/Volar 插件) |
| Docker | 数据库/部署 |

<div class="note-tip">
详细安装步骤见 <code>doc/doc_ch/开发部署/环境配置/</code> 目录。
</div>
