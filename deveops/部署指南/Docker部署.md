# Docker 部署

基于 `code/backend/server_py/tools/docker_compose` 编排的一键部署。

## 1. 编排内容

`docker-compose.yml` 包含以下服务：

| 服务 | 镜像 | 端口(宿主机:容器) | 用途 |
| :--- | :--- | :--- | :--- |
| nginx | nginx:alpine | 80:80 | 前端静态托管 + 后端反代 |
| postgis | postgis/postgis:17-3.5 | 15432:5432 | PostgreSQL + PostGIS/pgvector |
| redis7 | redis:7.2.4 | 6379:6379 | 可选缓存 |
| server_py | server_py:1.0.0 | 8600:8600 | 后端 API |

目录挂载约定(相对 `tools/docker_compose/`)：

```
docker_compose/
├── nginx/
│   ├── html/        # 前端构建产物(vue3 dist/*)
│   ├── conf/        # nginx 配置(覆盖 /etc/nginx/)
│   └── download/    # 静态下载资源
├── postgresql/
│   ├── data/        # 数据库数据目录(务必持久化备份)
│   └── init/        # 首次初始化 SQL(仅建库时执行)
├── redis/
│   ├── data/
│   └── redis.conf
└── server_py/
    ├── config.yaml        # 挂载覆盖容器内配置
    ├── config.dev.yaml
    ├── src/               # 源码挂载(热更新场景)
    ├── log/               # 日志落盘
    └── temp/ source/ books/   # 运行期文件目录
```

## 2. 部署步骤

```bash
# ① 构建后端镜像(见《打包构建》)
cd code/backend/server_py
docker build -f tools/docker_dev/Dockerfile.dev -t server_py:1.0.0 .

# ② 构建前端并拷贝产物
cd code/frontend/vue3
pnpm i && pnpm run build
cp -r dist/* <部署机>/docker_compose/nginx/html/

# ③ 调整配置
#    - docker-compose.yml 中 POSTGRES_PASSWORD 等
#    - server_py/config.yaml 中 db 连接(容器网络内用容器名/网关)

# ④ 启动
cd tools/docker_compose
bash start.sh          # 或 docker compose up -d

# ⑤ 验证
docker compose ps
curl http://127.0.0.1:8600/template/docs   # 后端 Swagger
curl http://127.0.0.1/                     # 前端首页
```

## 3. nginx 反代要点

前端请求 `/base_server/*` 需反代到后端容器，示例片段：

```nginx
location /base_server/ {
    proxy_pass http://server_py:8600/;     # compose 网络内容器名
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    # 大文件上传
    client_max_body_size 200m;
    # SSE 流式对话(必须关闭缓冲)
    proxy_buffering off;
    proxy_read_timeout 300s;
}
```

## 4. 常用运维命令

```bash
bash start.sh       # 启动全部
bash stop.sh        # 停止
bash restart.sh     # 重启
bash clean.sh       # 清理(谨慎,确认数据卷后再执行)

# 查看后端日志
docker logs -f server_py --tail 200
# 或挂载目录直接看
tail -f server_py/log/*.log
```

## 5. 常见问题

| 现象 | 处理 |
| :--- | :--- |
| 后端连不上数据库 | compose 网络内应使用服务名 `postgis`；宿主机库用 `host.docker.internal`(Linux 需 compose 中的 `extra_hosts` 行) |
| 上传大文件 413 | nginx `client_max_body_size` 与后端 `file_system.max_size` 同时调大 |
| AI 对话不流式 | nginx 该 location 必须 `proxy_buffering off` |
| 改了 src 不生效 | 源码挂载仅热加载源码，依赖变化需重建镜像 |

## 相关

- [打包构建](./打包构建.md)
- [数据库运维](../运维手册/数据库运维.md)
