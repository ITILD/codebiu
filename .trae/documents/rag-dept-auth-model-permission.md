# RAG 知识库：部门授权 + 模型配置权限 实施计划

## Context（背景与目标）

RAG 知识库已有 GitHub 式项目权限：创建者自动成为 `project_admin`（`ProjectService.add` 已实现）、成员邀请与三档角色（project_admin/editor/reader）已有完整 CRUD。本次补齐两块：

1. **按部门授权**：项目管理员可将"某部门 + 档位"授权进知识库，部门用户自动继承（级联子部门）；部门档位与个人档位**取最高档**生效。
2. **模型配置权限**：`ModelConfig`（用户私有、含 api_key）的 `get_llm` 按任意 model_id 取用无归属校验，存在越权使用他人 api_key 的风险。加**归属校验 + is_public 共享标记**。

已确认决策：档位取最高；部门授权级联子部门（利用 `Dept.ancestors`）；模型配置做归属校验+共享标记。

## 探索确认的关键事实

- **rag 控制器未挂载**：`src/app.py` 中 `from module_rag.controller import (...)` 整块被注释，实测 `/rag/project-members/my` 返回 404。**必须先恢复**，否则本需求 API 全部不可达。
- **实际数据库为 PostgreSQL**（config.dev.yaml: 47.94.107.62:20001，`is_dev: true`）。
- 建表走 `lifespan.py` → `table_create_all()`（SQLModel `table=True` 自动建表，无 alembic）；存量表补列有 `module_geometry/config/server.py` 的 `register_init_hook` 先例（但用了 Postgres 专有 `IF NOT EXISTS`，本方案用 inspector 检查更稳）。
- 部门树接口 `/authorization/depts/tree` 需要 `sys:dept:read`——普通项目管理员（知识库创建者）没有此权限码，**需在 rag 侧提供免 sys 权限的部门树端点**。
- `check_project_permission`（`module_rag/dependencies/permission.py`）：admin 穿透 → 成员档位 → 公开项目只读；`ACTION_LEVELS` 已含 invite/update/remove（档位3），无需改动。
- `DeptDao` 构建 ancestors（根="0"，子="0,<父id>"）；User 表有 `dept_id`。
- `UserModelService.get_llm_by_user_id()` 是 rag 问答/向量化的模型入口（内部 try/except 吞异常返回 None）。
- 前端 member.vue 现有结构：页头(返回/项目名/添加成员按钮) + TableSearchBar + 成员表格 + 添加成员对话框；部门树选择可参考 `src/modules/authorization/pages/user.vue` 的 `el-tree-select` 写法。

## 一、后端改动

### 1.1 恢复控制器挂载（前提）

`src/app.py`：
- 取消注释并整理 `from module_rag.controller import (conversation, project, project_document, project_document_chunk, project_member, rag_chat, user_model)` + 新增 `project_dept`
- module_ai 仅恢复模型配置管理：`from module_ai.controller import model_config`（chat/voice/ocr 保持注释）

### 1.2 新增 project_dept 七层（照抄 project_member 模式）

| 文件 | 内容 |
| ---- | ---- |
| `src/module_rag/do/project_dept.py` | `ProjectDept` 表(project_id, dept_id, role 三档, created_at/updated_at 同构 ProjectMember)；`ProjectDeptCreate`/`ProjectDeptUpdate(role)`/`ProjectDeptResponse` |
| `src/module_rag/dao/project_dept.py` | `add/get/get_by_project_and_dept/update/delete/list_by_project/count_by_project/delete_by_project/list_roles_by_dept_ids(project_id, dept_ids)->list[str]`（鉴权专用），签名风格对齐 `ProjectMemberDao` |
| `src/module_rag/service/project_dept.py` | `add`：role 合法性 + 部门存在性(`DeptDao`) + 重复授权查重；其余透传 + 分页组装 |
| `src/module_rag/dependencies/project_dept.py` | `get_project_dept_service`，照抄 project_member 依赖模式 |
| `src/module_rag/controller/project_dept.py` | 挂载 prefix=`/project-depts`。`POST ""`(invite 档位校验)、`GET /project/{project_id}`(read)、`PUT /{id}`(update)、`DELETE /{id}`(remove)，全部走 `enforce_project_permission(..., "member", act)`；**额外新增 `GET /dept-tree`（仅需登录，不设档位）**：内部调用 `DeptService.get_tree()` 返回部门树，解决普通项目管理员无 `sys:dept:read` 的问题。注意 `/project/{project_id}` 与 `/dept-tree` 声明在 `/{id}` 之前 |

### 1.3 鉴权链合并（`src/module_rag/dependencies/permission.py` 核心）

```python
# 新增: 用户部门链(祖级 ancestors + 自身, 去掉根占位"0")
async def get_user_dept_chain(user_id) -> list[str]:
    user = await UserDao().get(user_id)   # 复用 module_authorization.dao.user.UserDao
    dept = await DeptDao().get_raw(user.dept_id) if user?.dept_id else None
    chain = [d for d in dept.ancestors.split(",") if d and d != "0"] + [dept.id]

# 新增: 部门授权档位(链上命中授权的最高档)
async def get_dept_role_level(user_id, project_id) -> int:
    roles = await ProjectDeptDao().list_roles_by_dept_ids(project_id, await get_user_dept_chain(user_id))
    return max((RagRole.level(r) for r in roles), default=0)

# check_project_permission 第 2 步改为:
member_level = ...(原有成员查询)
dept_level = await get_dept_role_level(user_id, project_id)   # 新增
if max(member_level, dept_level) >= ACTION_LEVELS.get(act, 3): return True   # 取最高档
```

### 1.4 模型配置归属校验 + 共享标记

- `src/module_ai/do/model_config.py`：`ModelConfigBase` 加 `is_public: bool = Field(default=False, description="共享标记(True=所有用户可用)")`；`ModelConfigUpdate` 加 `is_public: bool | None = None`
- `src/module_ai/config/server.py`：新增 `register_init_hook` 幂等补列（inspector 检查列不存在则 `ALTER TABLE model_config ADD COLUMN is_public BOOLEAN NOT NULL DEFAULT FALSE`，用 `db_manager.db_rel.engine.begin()` + `conn.execute(text(...))`，不依赖 db_rel.exec/execute 差异）
- `src/module_rag/service/user_model.py`：
  - 新增 `_validate_model_access(model_id, user_id)`：配置不存在 → ValueError；归属本人 或 `is_public` 或 casbin 全局 admin(`enforcer.has_grouping_policy(user_id,"admin","*")`) → 放行；否则 ValueError
  - `upsert`：对三个非 None model_id 逐一校验
  - `get_llm_by_user_id`：取 binding 后先校验再 `get_llm`（校验失败被现有 try/except 捕获，logger.error 记录原因，返回 None，行为兼容）
- `src/module_rag/controller/user_model.py`：`PUT /my` 加 `except ValueError` → 400

### 1.5 项目删除级联

`src/module_rag/service/project.py` `delete()`：在删成员记录后插入 `await self.dept_auth_dao.delete_by_project(project_id, session=session)`；构造器注入 `ProjectDeptDao`

## 二、前端改动（code/frontend/vue3）

### 2.1 `src/modules/rag/api/deptAuth.ts`（新建）

`addProjectDept / listProjectDepts / updateProjectDept / removeProjectDept / getDeptTree`(→ `/rag/project-depts/dept-tree`)，http 封装对齐 `member.ts`

### 2.2 `src/modules/rag/types/index.ts`

追加 `ProjectDept / ProjectDeptCreate / ProjectDeptUpdate` 类型；角色选项复用 `ragRoleOptions`

### 2.3 `src/modules/rag/pages/member.vue`（Tab 改造）

- 页头不变；主体包进 `el-tabs`：
  - **个人成员** Tab：现有搜索栏+表格+分页整体平移
  - **部门授权** Tab：`el-tree-select`(check-strictly, 提示"子部门自动继承") + 角色下拉 + 添加授权按钮；已授权部门表格（部门名/档位 el-select 即改/授权时间/移除）+ 分页；底部提示文案"部门授权与个人成员档位取最高档生效"
- script：`activeTab` 懒加载（首次切到 depts 才拉部门树与授权列表）；部门名用前端 `deptMap`（树铺平 Map，与现有 userMap 模式一致）；部门树接口 403/失败时提示并禁用选择器，不影响成员 Tab

### 2.4 `src/modules/ai/pages/model_config.vue`

表单加"共享给所有用户"开关（is_public），列表加共享标记 tag（页面已存在，控制器恢复挂载后即可用）

## 三、文档更新

`doc/dev/permission.md`：
- 新增小节"项目级部门授权"：project_dept 表、鉴权合并规则（admin → max(个人, 部门链) → 公开只读）、ancestors 级联语义与"移动部门不刷新子孙 ancestors"局限、免 sys 权限的 `/rag/project-depts/dept-tree` 说明
- FAQ 追加"模型配置为什么别人绑不了"（is_public 共享标记 + 归属校验规则）

## 四、验证

1. 重启后端：确认启动无错（rag/ai 控制器恢复导入），日志确认 `project_dept` 表创建、`is_public` 补列执行且二次重启幂等
2. 接口冒烟（/docs + admin token）：`POST /rag/project-depts` → 201；重复/伪造 dept_id → 400；列表/改档位/删除 → 正常；`GET /rag/project-depts/dept-tree` 普通用户可访问
3. 鉴权链：给部门授权 reader → 该部门子部门下用户（非直连成员）访问项目 → 放行；删除授权 → 403；部门 reader + 个人 editor → 可上传（取 max）
4. 模型权限：用户 B 绑定用户 A 的非公开模型 → 400；A 设 is_public 后 → 200；rag 问答正常
5. 前端 `npm run type-check` 通过；浏览器验证 member.vue 两个 Tab 的增删改查与降级提示
6. 权限回归：权限管理页 rag 节点无新增按钮码（本次不加新权限码，部门授权复用 rag:member:invite/update/remove）
