# deveops 部署运维文档

项目部署与运维知识库，面向运维人员和需要自行部署的开发者。

## 目录导航

| 文档 | 内容 |
| :--- | :--- |
| [环境准备](./部署指南/环境准备.md) | 服务器基础环境( Docker / PostgreSQL / Nginx ) |
| [Docker 部署](./部署指南/Docker部署.md) | docker compose 一键部署前后端全家桶 |
| [打包构建](./部署指南/打包构建.md) | 后端镜像构建 / Nuitka 编译 / 前端构建 |
| [数据库运维](./运维手册/数据库运维.md) | 备份恢复、迁移、向量库扩展 |
| [发布流程](./运维手册/发布流程.md) | 版本发布与回滚步骤 |

## 架构总览

```mermaid
graph TD
    U[用户浏览器] -->|80/443| N[nginx]
    N -->|静态文件| FE[前端 dist(html)]
    N -->|/base_server 反代| S[server_py 容器]
    S -->|SQL| DB[(postgis 17)]
    S -.->|可选缓存| R[(redis 7)]
    S -->|文件存储| FS[本地挂载 / rustfs(S3)]
```

## 快速开始(最小部署)

```bash
# 1. 准备 docker 环境
docker --version && docker compose version

# 2. 进入部署编排目录
cd code/backend/server_py/tools/docker_compose

# 3. 按需修改 docker-compose.yml 中的密码/库名

# 4. 启动全部服务
bash start.sh        # 等价 docker compose up -d

# 5. 查看状态
docker compose ps
```

## 相关资源

- 后端工具脚本：`code/backend/server_py/tools/`
- 版本记录：`code/backend/server_py/doc/tag_doc/`
- 开发文档：`../doc/doc_ch/`
