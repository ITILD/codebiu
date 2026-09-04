# 权限设计

## 系统架构概述

本系统采用 **两级内置角色 + 模块权限自治声明 + 项目级成员档位** 模型（若依/GitHub 式），职责划分：

| 层级 | 负责内容 | 位置 |
|------|----------|------|
| **module_authorization(基础权限中心)** | 鉴权基建(casbin/依赖工厂)、用户/角色/权限/策略的管理接口、系统基础权限(sys/main 域)声明 | `config/registry.py`、`config/module_permissions.py` |
| **各业务模块(自治声明)** | 本模块涉及的权限树与新用户默认权限,在模块自己的 config 中声明 | 如 `module_rag/config/permissions.py`、`module_blog/config/permissions.py` |
| **业务模块项目级鉴权** | 基于成员表固定档位判断,不走 casbin | 如 `module_rag/dependencies/permission.py` |

支持的权限层级：

| 层级 | 权限范围 | 说明 |
|------|----------|------|
| **全局管理员(admin)** | 全局所有权限 | 内置角色,策略穿透一切；系统首个注册用户自动引导为该角色 |
| **普通用户(user)** | 各模块声明的基础权限 | 内置角色,新注册用户自动绑定,策略为各模块 `default_policies` 合集 |
| **自建角色** | 由管理员在界面勾选 | 基于 role/permission 表与权限树,满足细分场景 |
| **项目级角色** | 项目域内隔离 | 写死三档 `project_admin/project_editor/project_reader`,存业务模块成员表(如 `project_member.role`),不可分配不可扩展 |

### 项目私有化

- 项目公有时所有登录用户都可以只读访问项目资源
- 项目默认私有，只有项目成员才能访问项目详情与资源
- 隔离方式: 项目级鉴权查成员表档位(见 `module_rag/dependencies/permission.py`),不再使用 casbin 项目域

---

## 一、核心设计原则

| 原则 | 说明 | 反模式警示 |
|------|------|------------|
| **声明式权限** | 模块在自身 config/permissions.py 声明权限树与默认权限，启动幂等同步 | 禁止把业务模块策略硬编码在授权模块里 |
| **显式动作校验** | 路由层声明 `obj` + `act`，Casbin 负责匹配 | 禁止在代码中写死 `if role == "admin": pass` |
| **角色与权限解耦** | 权限绑定至角色，用户仅绑定角色 | 禁止为每个用户单独写入策略表 |
| **依赖注入拦截** | FastAPI `Depends` 前置拦截，业务层零权限逻辑 | 禁止在路由函数内部调用 `enforce()` |
| **项目档位内聚** | 项目内权限由业务模块成员表自判 | 禁止把项目成员关系写入 casbin |

---

## 二、权限注册中心(模块自治的核心)

`config/registry.py` 提供 `PermissionRegistry` 单例，业务模块按以下模式接入：

```python
# module_xxx/config/permissions.py
from module_authorization.config.registry import (
    ModulePermissionDefine, PermNode, permission_registry,
)

XXX_DEFINE = ModulePermissionDefine(
    module="xxx",               # 模块域名(权限树根节点 code)
    name="模块名",
    nodes=[                     # 权限树: M目录 > C菜单 > F按钮
        PermNode(name="资源管理", code="xxx:res", menu_type="C", path="/_sys/xxx/res",
            children=[
                PermNode(name="查询", code="xxx:res:read", menu_type="F"),
                PermNode(name="新增", code="xxx:res:create", menu_type="F"),
            ]),
    ],
    # 新用户默认权限(并入内置 user 角色策略),每项为 (域, 资源, 动作)
    default_policies=[("xxx", "res", "read")],
)
permission_registry.register(XXX_DEFINE)
```

**权限码(code)约定**（按钮级权限码即 casbin 四元组的直接映射）：

| 层级 | 格式 | 示例 | casbin 映射 |
|------|------|------|-------------|
| 目录 | `模块` | `rag` | 无(仅分组) |
| 菜单 | `模块:资源` | `rag:project` | 无(仅分组) |
| 按钮 | `模块:资源:动作` | `rag:project:create` | `(角色, rag, project, create)` |

**注册时机**：模块的 `config/server.py`(或 app.py 导入链上的任意入口)导入 permissions.py 即完成注册；启动时 `AuthManager.init_default_casbin()` 统一幂等同步：

1. **casbin 策略表**：全局 `admin` 通配策略 + 内置 `user` 角色的默认权限合集
2. **role 表**：upsert 内置角色 admin/user(供角色管理界面)
3. **permission 表**：按 code upsert 权限树(供权限管理/角色授权界面)

---

## 三、Casbin 模型配置（`rbac_model.conf`）

```ini
[request_definition]
r = sub, dom, obj, act

[policy_definition]
p = sub, dom, obj, act

[role_definition]
g = _, _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = (g(r.sub, p.sub, r.dom) || g(r.sub, p.sub, "*")) && \
    (r.dom == p.dom || p.dom == "*" || keyMatch(r.dom, p.dom + "/*")) && \
    (r.obj == p.obj || p.obj == "*") && (r.act == p.act || p.act == "*")
```

**匹配器说明**：
- `g(r.sub, p.sub, r.dom)`：检查用户在请求域内是否具有策略角色
- `g(r.sub, p.sub, "*")`：检查用户是否具有全局角色（内置角色绑定统一存全局域 "*"）
- `r.dom == p.dom`：域内策略匹配
- `p.dom == "*"`：全局策略匹配（admin 穿透）
- `keyMatch(r.dom, p.dom + "/*")`：父域策略作用于子域（保留匹配能力,当前项目级权限已不走 casbin）

**域划分约定**：
- `*` 全局域(内置角色绑定)；`sys` 授权模块域；`main` 基础资源域(字典/数据库/文件/搜索)
- `rag` 知识库模块域；`blog` 博客模块域

---

## 四、FastAPI 权限依赖层

**全局/模块级**（`module_authorization/dependencies/permission.py`）：

```python
# 模块级校验(域 = 模块名)
@router.post("", dependencies=[Depends(require_permission("rag", "project", "create"))])

# 服务层手动校验
await enforce_permission(user_id, "rag", "project", "create")
```

**项目级**（业务模块自建,如 `module_rag/dependencies/permission.py`,基于成员表档位）：

```python
# 项目级校验(路径含 {project_id},按 project_member.role 档位判断)
@router.post("/{project_id}/upload", dependencies=[Depends(require_project_permission("doc", "upload"))])

# 服务层手动校验(已知 project_id 的场景)
await enforce_project_permission(user_id, project_id, "doc", "delete")
```

其他常用能力：
- `sync_default_user_roles(user_id, is_first_user)`：新用户绑定内置 user 角色；首个注册用户自动引导为全局管理员
- `GET /authorization/auth/me-permissions`：返回当前用户角色(按域分组)与权限码列表(全局管理员返回 `["*"]`)

---

## 五、角色授权管理（前端）

- `GET /authorization/casbin-rules/module-tree`：全部模块声明的权限树（可分配权限集合）
- `POST /authorization/casbin-rules/role-perms`：`{role_key, codes}` 全量同步角色节点级权限——仅处理权限树按钮节点对应策略，内置角色的通配策略(如 `admin/*/*/*`、`main/*` read)不受影响
- 前端 `usePermission()` 组合式函数：`hasPerm("rag:project:create")` 按钮级控制、菜单按权限码过滤

---

## 六、权限矩阵（示例：知识库模块）

| 操作 | admin | user(非成员) | project_admin | project_editor | project_reader |
|------|-------|-------------|---------------|----------------|----------------|
| 查看项目列表 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 创建项目 | ✅ | ✅ | - | - | - |
| 修改/删除项目 | ✅ | ❌(公开项目只读) | ✅ | ❌ | ❌ |
| 邀请/移除成员 | ✅ | ❌ | ✅ | ❌ | ❌ |
| 查看文档 | ✅ | 仅公开项目 | ✅ | ✅ | ✅ |
| 上传/修改文档 | ✅ | ❌ | ✅ | ✅ | ❌ |
| 删除文档 | ✅ | ❌ | ✅ | ❌ | ❌ |
| 知识库问答 | ✅ | ✅(模块级) | ✅ | ✅ | 只读 |

> 项目级档位权限由 `module_rag/dependencies/permission.py` 的 `ACTION_LEVELS` 定义；
> 自建角色可授予模块级权限码(如 `rag:project:delete`),但项目内资源操作仍以成员档位为准。

---

## 七、生产环境关键实践

| 维度 | 建议方案 |
|------|----------|
| **策略持久化** | `casbin_async_sqlalchemy_adapter`，`g` 表存 `用户-角色-域`，`p` 表存角色策略，与业务共用 DB 连接 |
| **热更新机制** | 策略变更时调用 `POST /casbin-rules/reload-policy`，或结合 Redis Pub/Sub 通知多节点刷新内存策略 |
| **性能优化** | `me-permissions` 结果可缓存至 Redis，TTL 随策略版本号失效 |
| **审计日志** | 在 `require_permission` 依赖中注入 `logging`，记录 `(uid, dom, obj, act, result, timestamp)` 至独立审计表 |
| **越权测试** | 单元测试覆盖非成员调用项目 `delete` 接口的场景，验证 `403` 拦截与档位判断是否生效 |

---

## 结论

最优设计遵循 **模块自治声明 + 两级内置角色 + 项目档位内聚** 架构：
1. 各模块在自身 `config/permissions.py` 声明权限树与新用户默认权限，授权模块零侵入扩展
2. 全局只维护 admin/user 两个内置角色，细分场景由管理员自建角色勾选权限码
3. 项目内权限由业务模块成员表固定档位自判，鉴权少一层策略同步，语义与主流 SaaS(GitHub/Notion)一致

该架构可直接支撑万级项目、十万级用户的知识库权限管控，且后续新增业务模块（如 blog）仅需在模块内新建 `config/permissions.py` 并注册，无需改动核心鉴权链路。
