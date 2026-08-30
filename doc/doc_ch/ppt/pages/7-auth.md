---
layout: two-cols
layoutClass: gap-8
---

# 权限体系：Casbin RBAC

## 模型

```
域(dom)划分:
  "*"              全局域(系统管理员)
  "main"           主模块域
  "rag:{proj_id}"  知识库项目域(多用户隔离)
```

角色: `main_admin` / `main_operator` / `main_viewer` ...

## 路由上声明权限

```python
from module_authorization.dependencies.permission \
    import require_permission

@router.get("/list")
async def list_files(
    user_id: str = Depends(
        require_permission("main", "file", "read")
    ),
):
    ...
```

::right::

## 前置约定

| 动作 | 含义 |
| :---: | :--- |
| `read` | 查看/下载 |
| `create` | 新建/上传 |
| `update` | 改名/移动 |
| `delete` | 删除 |

## 新模块接入步骤

1. 在 `casbin_rule.py` 的 `MAIN_POLICY_PRESET`
   中**声明角色规则**
2. 控制器路由挂 `require_permission`
3. 前端无需感知(403 自动提示)

<div class="note-tip">
规则启动时幂等写入,声明式配置,改完重启即生效。
</div>
