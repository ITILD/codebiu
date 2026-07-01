# 权限设计

## 系统架构概述

本系统采用 **域隔离 RBAC 模型**，支持以下权限层级：

| 角色 | 权限范围 | 说明 |
|------|----------|------|
| **系统管理员** | 全局所有权限 | 通过全局角色 `admin` 在 `*` 域实现权限穿透 |
| **项目管理员** | 项目内全部操作 | 可管理项目配置、上传/删除文档、邀请成员 |
| **普通成员** | 项目内只读 | 仅可查看和读取项目文档 |

### 项目私有化

- 项目公有时所有普通成员都可以只读访问项目文档
- 项目默认私有，当项目设定为私有时，只有项目管理员和项目成员才能看到列表和访问项目详情
- 通过域（domain）隔离实现项目间权限隔离

---

## 一、核心设计原则

| 原则 | 说明 | 反模式警示 |
|------|------|------------|
| **显式动作校验** | 路由层声明 `obj` + `act`，Casbin 负责匹配 | 禁止在代码中写死 `if role == "admin": pass` |
| **角色与权限解耦** | 权限绑定至角色模板，用户仅绑定角色 | 禁止为每个用户单独写入策略表 |
| **依赖注入拦截** | FastAPI `Depends` 前置拦截，业务层零权限逻辑 | 禁止在路由函数内部调用 `enforce()` |
| **域级隔离+全局穿透** | 项目为域，系统管理员通过 `*` 域豁免 | 禁止混用多套鉴权中间件 |

---

## 二、Casbin 模型配置（`rbac_model.conf`）

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
# 支持域内角色匹配与全局角色（*）穿透
m = (g(r.sub, p.sub, r.dom) || g(r.sub, p.sub, "*")) && \
    (r.dom == p.dom || p.dom == "*") && \
    r.obj == p.obj && r.act == p.act
```

**匹配器说明**：
- `g(r.sub, p.sub, r.dom)`：检查用户在请求域内是否具有策略角色
- `g(r.sub, p.sub, "*")`：检查用户是否具有全局角色（系统管理员）
- `r.dom == p.dom`：域内策略匹配
- `p.dom == "*"`：全局策略匹配（系统管理员权限穿透）

---

## 三、角色模板初始化

系统启动时执行一次，预置角色权限模板：

```python
def init_role_templates() -> None:
    """初始化角色权限模板（仅系统启动调用一次）"""
    templates = [
        # (角色, 域, 对象, 动作)
        # 普通成员：只读权限
        ("reader", "*", "doc", "read"),
        ("reader", "*", "project", "read"),
        
        # 项目管理员：项目操作 + 文档管理
        ("project_admin", "*", "project", "read|update|delete|manage"),
        ("project_admin", "*", "doc", "read|upload|update|delete"),
        
        # 系统管理员：全局所有权限
        ("admin", "*", "*", "*"),
    ]
    for role, dom, obj, acts in templates:
        for act in acts.split("|"):
            enforcer.add_policy(role, dom, obj, act)
    enforcer.save_policy()
```

**调用时机**：应用启动钩子 `@app.on_event("startup")` 或独立迁移脚本。

---

## 四、权限分配流程

### 1. 创建项目

```python
@app.post("/api/projects")
def create_project(
    name: str,
    uid: str = Depends(get_current_user)
) -> dict[str, str]:
    """创建项目（默认所有人可调用，创建者自动成为项目管理员）"""
    project_id = f"proj_{name.lower().replace(' ', '_')}"
    
    # 绑定用户至项目域的管理员角色
    enforcer.add_grouping_policy(uid, "project_admin", project_id)
    enforcer.save_policy()
    return {"status": "created", "project_id": project_id}
```

### 2. 邀请成员

```python
@app.post("/api/projects/{project_id}/members")
def invite_member(
    target_uid: str,
    role: str,  # 仅允许 "reader" 或 "project_admin"
    _: None = Depends(require_access("project", "manage"))
) -> dict[str, str]:
    """邀请成员（需项目管理员权限）"""
    if role not in ("reader", "project_admin"):
        raise HTTPException(status_code=400, detail="角色不合法")
    enforcer.add_grouping_policy(target_uid, role, project_id)
    enforcer.save_policy()
    return {"status": "invited", "role": role}
```

### 3. 分配系统管理员

```python
def assign_sys_admin(user_id: str) -> None:
    """将用户设置为系统管理员"""
    enforcer.add_grouping_policy(user_id, "admin", "*")
    enforcer.save_policy()
```

---

## 五、FastAPI 权限依赖层

```python
from fastapi import FastAPI, Depends, HTTPException, status, Path
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import casbin

app = FastAPI(title="Knowledge-Base-API")
security = HTTPBearer()

enforcer = casbin.Enforcer("rbac_model.conf", casbin.FileAdapter("policies.csv"))

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """提取 Token 中的用户标识"""
    return creds.credentials

def require_access(obj: str, act: str):
    """通用权限校验依赖（自动提取项目域）"""
    def _verify(project_id: str = Path(...), uid: str = Depends(get_current_user)) -> None:
        if not enforcer.enforce(uid, project_id, obj, act):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    return _verify
```

---

## 六、核心业务接口实现

```python
@app.get("/api/projects/{project_id}/docs")
def list_docs(_: None = Depends(require_access("doc", "read"))) -> list[str]:
    """文档列表（reader / project_admin / admin 均可访问）"""
    return ["spec.md", "changelog.json"]

@app.post("/api/projects/{project_id}/docs")
def upload_doc(_: None = Depends(require_access("doc", "upload"))) -> dict[str, str]:
    """上传文档（仅 project_admin）"""
    return {"status": "uploaded"}

@app.put("/api/projects/{project_id}/config")
def update_config(_: None = Depends(require_access("project", "update"))) -> dict[str, str]:
    """修改项目配置（仅 project_admin）"""
    return {"status": "updated"}

@app.delete("/api/projects/{project_id}")
def delete_project(_: None = Depends(require_access("project", "delete"))) -> dict[str, str]:
    """删除项目（仅 project_admin）"""
    return {"status": "deleted"}
```

---

## 七、权限矩阵

| 操作 | 系统管理员 | 项目管理员 | 普通成员 |
|------|-----------|-----------|---------|
| 查看项目 | ✅ | ✅ (本域) | ✅ (本域) |
| 修改项目配置 | ✅ | ✅ (本域) | ❌ |
| 删除项目 | ✅ | ✅ (本域) | ❌ |
| 邀请成员 | ✅ | ✅ (本域) | ❌ |
| 查看文档 | ✅ | ✅ (本域) | ✅ (本域) |
| 上传文档 | ✅ | ✅ (本域) | ❌ |
| 删除文档 | ✅ | ✅ (本域) | ❌ |

---

## 八、生产环境关键实践

| 维度 | 建议方案 |
|------|----------|
| **策略持久化** | 使用 `casbin_sqlalchemy_adapter`，`g` 表存 `用户-角色-域`，`p` 表存角色模板。业务事务与 Casbin 写入共用 DB 连接 |
| **热更新机制** | 策略变更时调用 `enforcer.load_policy()`，或结合 Redis Pub/Sub 通知多节点刷新内存策略 |
| **性能优化** | 高频接口启用 `enforcer.enable_auto_save(False)` 批量提交；将 `(uid, dom, obj, act)` 结果缓存至 Redis，TTL 随策略版本号失效 |
| **审计日志** | 在 `require_access` 依赖中注入 `logging`，记录 `(uid, dom, obj, act, result, timestamp)` 至独立审计表 |
| **越权测试** | 单元测试覆盖 `g(user, reader, proj_x)` 但调用 `delete` 接口的场景，验证 `403` 拦截是否生效 |

---

## 结论

最优设计遵循 **显式动作声明 + 角色模板化 + 依赖注入拦截** 三位一体架构：
1. 路由层仅声明 `obj` 与 `act`，保持业务逻辑纯净
2. 权限收敛至角色模板，用户仅关联角色，策略数据可版本化管理
3. 依赖工厂自动提取路径参数并完成 Casbin 校验，兼顾开发效率与安全边界

该架构可直接支撑万级项目、十万级用户的知识库权限管控，且后续新增细粒度权限（如分支级、文件级）仅需扩展 `obj` 命名空间，无需改动核心鉴权链路。
