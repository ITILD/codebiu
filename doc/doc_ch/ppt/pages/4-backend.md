---
glow: left
---

# 后端结构：MVC 分层

## 一个请求的生命周期

```mermaid {scale: 0.65}
graph TD
    A[用户请求] -->|调用| B[Controller 路由]
    B -->|调用| C[Service 业务]
    C -->|调用| D[DAO 数据访问]
    D -->|操作| E[(数据库)]

    F[dependencies 依赖注入] -.-> B
    F -.-> C
    F -.-> D

    G[DO 数据对象] -.->|传输| B
    G -.->|处理| C
    G -.->|持久化| D
```

## 各层职责

| 层 | 目录 | 职责 |
| :---: | :---: | :--- |
| Controller | `controller/` | 定义路由、参数校验、调 Service |
| Service | `service/` | 业务逻辑、事务(`@DaoRel`) |
| DAO | `dao/` | 数据库 CRUD 封装 |
| DO | `do/` | 表模型 + Pydantic 模型 |
| Config | `config/` | 模块路由挂载 + 配置 |
| Dependencies | `dependencies/` | FastAPI 依赖注入工厂 |

<div class="note-tip">
事务约定: DAO 方法加 <code>@DaoRel</code> 装饰器自动管理 session, Service 直接调用即可。
</div>
