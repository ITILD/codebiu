# 权限体系说明与新模块接入指南

> 适用范围: `server_py` 后端权限体系(RBAC + Casbin) 与前端 `vue3` 菜单/按钮过滤。
> 相关代码: `src/module_authorization/`(权限基建) + 各模块 `config/permissions.py`(模块自治声明)。

## 一、总体架构

```
┌────────────┐  登录/JWT   ┌──────────────┐  enforce(user,dom,obj,act)  ┌─────────────┐
│ 前端 vue3   │ ─────────→ │ FastAPI 接口  │ ──────────────────────────→ │ Casbin 引擎  │
│ usePermission│           │ require_permission │                        │ casbin_rule 表│
└────────────┘             └──────────────┘                             └─────────────┘
       │ 权限码列表(/auth/permission-info)                                      ↑
       └── 菜单/按钮过滤                        模块声明(ModulePermissionDefine) ─┘
                                            启动时幂等同步 casbin/role/permission 表
```

### 1.1 角色体系(两级内置 + 自建)

| 角色 | role_key | 策略 | 说明 |
| ---- | -------- | ---- | ---- |
| 系统管理员 | `admin` | `("admin","*","*","*")` | 穿透一切,权限码返回 `["*"]` |
| 普通用户 | `user` | 各模块 `default_policies` 声明合集 | 新注册用户自动绑定 |
| 自建角色 | 任意 key | 管理员在界面勾选 | 角色管理→分配权限 |

### 1.2 权限码约定

```
"模块"             目录节点(M)  如 "rag"
"模块:资源"         菜单节点(C)  如 "rag:project"
"模块:资源:动作"    按钮节点(F)  如 "rag:project:create"
```

按钮级权限码可直接解析为 casbin 策略四元组 `(sub=角色, dom=模块, obj=资源, act=动作)`。
后端接口用 `require_permission("模块", "资源", "动作")` 校验;前端 `hasPerm("模块:资源:动作")` 控制按钮显隐。

### 1.3 数据表

| 表 | 作用 | 维护方 |
| ---- | ---- | ---- |
| `casbin_rule` | 策略(p: 角色-域-资源-动作) + 用户角色绑定(g) | 启动声明同步 + 管理界面 |
| `role` | 角色字典(admin/user 内置不可删) | 启动 upsert + 界面自建 |
| `permission` | 权限/菜单树(前端权限管理页展示) | 启动按声明 upsert + 界面微调 |

### 1.4 启动同步机制(幂等)

`module_authorization/config/casbin_rule.py` 的 `init_default_casbin()`:
1. 注册中心收集所有模块声明(模块 `config/permissions.py` 导入时注册);
2. **补写**缺失策略: admin 通配 + 各模块 `default_policies` 合并出的 user 策略(只增不减);
3. upsert 内置角色到 `role` 表、按 code upsert 声明树到 `permission` 表。

> **注意**: 声明中移除某条 `default_policies` **不会自动回收**已存在的 user 策略
> (避免误删管理员在界面手动分配的权限)。回收方式见第四节 FAQ。

## 二、部门 / 角色 / 人员 / 权限管理

全部位于 **权限管理** 分组(前端路由 `/authorization/*`, 域 `sys`),每项均为标准 CRUD 权限码:

| 页面 | 路由 | 权限码 | 说明 |
| ---- | ---- | ---- | ---- |
| 用户管理 | `/authorization/user` | `sys:user:read/create/update/delete` | 人员增删改查;**分配角色**按钮调用 casbin 用户-角色绑定接口(需 `sys:casbin:create`) |
| 角色管理 | `/authorization/role` | `sys:role:*` | 自建角色 + **分配权限**(勾选模块声明树按钮码) |
| 部门管理 | `/authorization/dept` | `sys:dept:*` | 部门树维护;`data_scope` 数据范围字段预留 |
| 权限管理 | `/authorization/permission` | `sys:permission:*` | 权限/菜单树查看与手动微调(树默认折叠) |
| 策略规则 | `/authorization/casbin` | `sys:casbin:*` | p/g 规则直接管理、权限测试 |

前端侧边栏按 `hasPerm("sys")` / `hasPerm("sys:user")` 过滤菜单;权限树(权限管理页、部门表、分配权限树)**默认不展开**,点击箭头逐级展开。

## 三、现有模块权限声明清单

| 模块域 | 显示名 | order | 菜单路径 | 新用户默认策略 |
| ---- | ---- | ---- | ---- | ---- |
| `sys` | 系统管理 | 1 | /authorization/* | 无 |
| `main` | 基础资源 | 2 | /main/*、/file | main:*:read |
| `rag` | 知识库 | 10 | /rag/* | project/chat 读写(历史遗留,可按需收敛);项目内权限见 4.2 部门授权 |
| `blog` | 博客 | 20 | /blog/* | 只读+评论(历史遗留) |
| `geometry` | 地理空间 | 25 | /geometry/earth | **无(新约定)** |
| `task` | 任务队列 | 30 | /task/queue | **无(新约定)** |

## 四、新加模块的权限处理(默认无权限)

**约定: 新加模块默认不带权限** —— 权限树照常声明(供管理界面展示与分配),但
`default_policies=[]`,普通用户默认看不到该模块菜单、接口返回 403;由管理员按需分配。

### 4.1 接入步骤(以 module_task 为范本)

```python
# 1. src/module_xxx/config/permissions.py
from module_authorization.config.registry import (
    ModulePermissionDefine, PermNode, permission_registry,
)

XXX_DEFINE = ModulePermissionDefine(
    module="xxx",                 # 模块域(=权限树根节点)
    name="模块显示名",
    icon="图标名",
    order_num=30,                 # 菜单/权限树排序
    description="...",
    nodes=[
        PermNode(
            name="资源管理",
            code="xxx:res",       # 菜单节点 C
            menu_type="C",
            path="/xxx/res",      # 前端路由(与 src/modules/xxx/pages 一致)
            children=[
                PermNode(name="查询", code="xxx:res:read",   menu_type="F"),
                PermNode(name="新增", code="xxx:res:create", menu_type="F"),
                PermNode(name="修改", code="xxx:res:update", menu_type="F"),
                PermNode(name="删除", code="xxx:res:delete", menu_type="F"),
            ],
        ),
    ],
    # ★ 默认新模块不带权限: 保持为空,由管理员在界面分配
    default_policies=[],
)

# 2. 注册(模块 config 导入时生效)
permission_registry.register(XXX_DEFINE)
```

```python
# 3. 控制器接口校验(src/module_xxx/controller/res.py)
from module_authorization.dependencies.permission import require_permission

@router.get("/list", dependencies=[Depends(require_permission("xxx", "res", "read"))])
async def list_res(...): ...
```

```python
# 4. app.py 导入模块时完成声明注册
from module_xxx.controller import res
from module_xxx.config import permissions as xxx_permissions  # noqa: F401
```

```typescript
// 5. 前端菜单(src/app/components/layout/SysSidebar.vue)声明 perm 后自动过滤
{ index: '/xxx', title: '模块名', perm: 'xxx',
  children: [{ index: '/xxx/res', title: '资源管理', perm: 'xxx:res' }] }
```

### 4.2 项目级部门授权(批量授权)

除逐个邀请成员外,项目管理员可把"某个部门 + 档位"整体授权进知识库
(`project_dept` 表: project_id / dept_id / role 三档),适合按组织批量开通:

- **级联继承**: 授权父部门时,利用 `dept.ancestors` 祖级链,其所有子部门用户自动继承
  (注意: 管理界面移动部门节点只重算本节点 ancestors,移动后的子树需重新授权或手动修数据);
- **档位合并**: 用户生效档位 = max(直连成员档位, 部门链命中最高档),
  例: 部门授权 reader + 个人邀请 editor → 按 editor 生效;
- **接口**: `/rag/project-depts` CRUD(档位校验复用项目成员的 invite/update/remove,
  即需 project_admin 档位),`GET /rag/project-depts/dept-tree` 提供仅供登录的部门树
  (普通项目管理员无 `sys:dept:read` 也能选择部门);
- **前端**: 知识库成员页"部门授权"Tab,部门树选择 + 档位 + 授权列表管理;
- 删除项目时部门授权记录随项目级联清理。

完整鉴权链(`module_rag/dependencies/permission.py`):
`全局 admin 穿透 → max(直连成员档位, 部门链档位) 达标放行 → 公开项目登录用户只读`。

### 4.3 模型配置权限(归属校验 + 共享标记)

模型配置(`model_config` 表,module_ai)为**用户私有资源**(含 api_key):

- 校验规则: 使用/绑定时要求 配置归属本人 **或** `is_public=true`(共享) **或** 全局管理员;
- 校验位置: `UserModelService._validate_model_access`,在
  绑定(`PUT /rag/user-models/my`,失败返回 400)与
  使用(`get_llm_by_user_id`,rag 问答/向量化入口)两处生效;
- 共享标记: 模型配置编辑对话框"共享"开关(AI 模块 /ai/model_config),
  设为公开后所有用户可绑定使用该配置(含其 api_key)。

### 4.4 给角色分配新模块权限

1. 管理员登录 → **权限管理 → 角色管理** → 目标角色(如"普通用户")→ **分配权限**;
2. 勾选新模块的按钮级权限码(树默认折叠,展开模块根节点勾选)→ 确认;
3. 相关用户**重新登录**(权限码在登录时计算并随 JWT 流程下发)后生效。

也可以在 **策略规则** 页直接维护 p/g 规则(等价于 casbin 四元组)。

### 4.3 FAQ

**Q: 修改了模块权限声明(加节点/改路径/删默认策略),如何生效?**
重启 API 服务即可,启动时幂等同步(新增 upsert + 策略补写)。历史数据说明:
- 新增节点: 自动写入 permission 表;
- 改 path/icon 等: 自动更新;
- **删除声明节点**: permission 表记录不会自动删除(保护手工调整),需在权限管理页手动删除;
- **删除 default_policies 条目**: casbin 中 user 角色已下发的策略不自动回收。

**Q: 如何回收 user 角色已下发的旧默认策略?**
方式一(推荐): 角色管理→分配权限→取消勾选→确认(全量同步该角色的节点级策略);
方式二(批量): 直接清理 casbin_rule 表(参考 `tools/cleanup_user_policies.py`):

```sql
DELETE FROM casbin_rule WHERE ptype='p' AND v0='user' AND v1='模块域';
```

**Q: 为什么普通用户有权限却看不到菜单?**
权限码在登录时下发,分配权限后需重新登录;或检查 SysSidebar 菜单项的 `perm` 是否与声明一致。

**Q: 为什么绑定不了别人的模型配置?**
模型配置是用户私有资源(含 api_key)。只能绑定 自己创建的 / 已设为共享(is_public) /
全局管理员提供的配置;需要共享时由配置创建者在 AI 模型配置页打开"共享"开关。详见 4.3 节。

**Q: 项目级/数据级权限?**
项目内权限不走 casbin(如 rag 的 project_member 固定档位);部门数据范围 `data_scope` 字段预留。
