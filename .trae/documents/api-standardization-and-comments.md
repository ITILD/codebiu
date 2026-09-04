# 接口规范化 + 注释补全 + 函数命名规范 实施计划

## Context（背景）

用户要求对整个项目（后端 server_py + 前端 vue3）进行三项治理：
1. **补全必要注释**（中文，符合用户规则"必要的方法和页面添加注释"）
2. **系统性规范化接口 URL**（用户已确认破坏性变更方案，前端 api 层 + 后端测试同步修改）
3. **规范函数名加强易读性**（前后端）

现状调查结论：
- 后端 ~230 条路由、15+ 模块，URL 风格混乱（snake_case 与 kebab-case 混用、单复数混用、`/list_all` 与 `/list` 并存、`/generate_presigned_url_upload` 超长命名、module_nlp 存在 `/nlp/nlp/synonyms` 双重前缀缺陷）
- controller/service 层约 108 个函数缺 docstring；dao 层与 common/utils 部分缺失
- 前端 23 个 api 文件集中封装所有请求（组件层零硬编码 URL），33 个页面注释普遍偏少
- 权限系统为纯 (dom, obj, act) 三元组，不依赖 URL，改名无权限影响

**统一 URL 规范**：路由前缀=复数名词+kebab-case；子路径 kebab-case；分页 `GET /list`、全量 `GET /all`、滚动 `GET /scroll`、树 `GET /tree`；动作端点保留 `POST /{id}/{action}`；查询辅助 `GET /by-xxx/{key}`。

---

## 阶段①：后端 URL 规范化 + 测试同步（~38 个文件）

### 1.1 prefix 级改名（include_router）

| 模块 | 旧 prefix | 新 prefix |
|---|---|---|
| module_main | `/server_status` | `/server-status` |
| module_authorization | `/token` | `/tokens` |
| module_authorization | `/casbin_rules` | `/casbin-rules` |
| module_rag | `/project-document-chunk` | `/project-document-chunks` |
| module_office | `/document_parse` | `/document-parse` |
| module_office | `/document_chunk`（空路由） | `/document-chunks` |
| module_ai | `/model_config` | `/model-configs` |
| module_ai | `/llm_base` | `/llm-base` |
| module_nlp | `/nlp/synonyms`（双重前缀缺陷） | `/synonyms`（消除 /nlp/nlp/ 冗余） |
| module_life | `/baby_name` | `/baby-names` |
| module_little_utils | `/todolist` | `/todolists` |
| module_dev_tools | `/template_strings` | `/template-strings` |
| module_template | `/template_ex`、`/template_async_learn` | `/template-ex`、`/template-async-learn` |

已规范保持不动：`/auth /users /roles /permissions /depts /dict_types /dict_items /db /tasks /conversations /projects /project-documents /project-members /project-depts /user-models /rag-chat /voice /ocr /translate /static /templates /features /filesystem /websearch`。

### 1.2 路径级改名（重点条目）

**module_main**：
- `/server_status/status_cache` → `/server-status/cache`
- `/server_status/sys_info|hardware_status|network_status|mount_count` → kebab 化
- `/dict_items/dict_type/{type_code}` → `/dict_items/by-type/{type_code}`
- `/dict_items/count/dict_type/{type_code}` → `/dict_items/by-type/{type_code}/count`

**module_authorization**：
- `/auth/me_id` → `/auth/me-id`；`/auth/me_permissions` → `/auth/me-permissions`
- `/auth/_token` → `/auth/token`（**必须同步改 `src/module_authorization/dependencies/auth.py` L11 的 `OAuth2PasswordBearer(tokenUrl="/authorization/auth/_token")`，否则 Swagger Authorize 静默失效**）
- `/token/revoke_all/{user_id}` → `/tokens/revoke-all/{user_id}`
- `/roles/list_all` → `/roles/all`

**module_file 预签名族（收拢到 /presigned/ 子空间）**：
- `POST /generate_presigned_url_upload` → `POST /presigned/upload-url`
- `PUT /presigned_url_upload/{file_path:path}` → `PUT /presigned/upload/{file_path:path}`
- `POST /presigned_url_upload_success` → `POST /presigned/upload-complete`
- `GET /generate_presigned_url_download/{file_id}` → `GET /presigned/download-url/{file_id}`
- `GET /presigned_url_download/{file_path:path}` → `GET /presigned/download/{file_path:path}`
- `DELETE /file/{id}` → `/files/{id}`；`DELETE /folder/{id}` → `/folders/{id}`；`GET /file_entry/{id}` → `/entries/{id}`
- `/list_dir` → `/list-dir`；`/list_by_path` → `/list-by-path`；`/mkdir_p` → `/mkdir-p`
- **关键同步点**：`src/module_file/service/filesystem.py` L877/L945 的 `presigned_url_path.replace("generate_", "")` 派生逻辑。推荐改为 controller 定义常量 `PRESIGNED_UPLOAD_PROXY_PATH`/`PRESIGNED_DOWNLOAD_PROXY_PATH` 直接传入 service，消除字符串魔法。

**module_ai**：
- `/model_config/default_params/{model_name}` → `/model-configs/default-params/{model_name}`
- `/llm_base/check_config|check_config_by_model_id` → `/llm-base/check-config|check-config-by-model-id`
- `DELETE /llm_base/_test_cache_clear/{model_id}` → `DELETE /llm-base/cache/{model_id}`（及无 id 全清分支 `/llm-base/cache`）
- `/ocr/tupu` → `/ocr/segments`（去拼音）；`/ocr/lang` → `/ocr/languages`；`/ocr/all_base64` → `/ocr/all-base64`

**module_rag**：
- `/project-documents/{document_id}/reparse_task` → `/reparse-task`
- `/project-document-chunk/chunks_by_question` → `/project-document-chunks/search-by-question`

**module_life**（prefix + 全部子路径 snake → kebab）：
- `/predict_name_info_preference` → `/predict-name-info-preference`、`/predict_baby_info_base` → `/predict-baby-info-base` 等

**module_office**：`/document_parse/get_markdown_by_file` → `/document-parse/get-markdown-by-file`；`/split_code` → `/split-code`

**module_template**：`/template_async_learn/async_sync/{id}/{duration_use}` → `/template-async-learn/async-sync/{id}/{duration-use}` 等（路径参数名同步改）

**module_nlp**：prefix 消除双重前缀后所有 URL 缩短一级；`/batch_group` → `/batch-group`

### 1.3 测试同步（16 个文件）
- `tests/module_main/controller/test_status.py`（/sys_info /status_cache）、`test_dict_item.py`（/dict_type/ → /by-type/）
- `tests/module_authorization/controller/test_token.py`（BASE → /tokens）、`test_auth.py`（me-id me-permissions /token）、`test_casbin_rule.py`（BASE → /casbin-rules）、`test_role.py`（/list_all → /all）
- `tests/module_ai/controller/test_model_config.py`、`test_llm_base.py`
- `tests/module_file/controller/test_filesystem.py`（L19-23 预签名 URL 常量）
- `tests/module_rag/controller/test_user_model.py`（AI_MODEL_BASE）
- `tests/module_life/controller/test_baby_name.py`、`tests/module_little_utils/controller/test_todolist.py`、`tests/module_dev_tools/controller/test_template_string.py`

### 验证
```
cd code\backend\server_py && .venv\Scripts\python.exe -m pytest tests -q   # 154 全绿
```
改名前先导出 openapi.json 快照，改后对比确认无遗漏。

---

## 阶段②：前端 URL 同步（~12 个文件）

api 层逐文件更新（组件层零改动，已确认无 URL 逃逸）：

| 文件 | 改动 |
|---|---|
| `ai/chat.ts` | `/ai/llm_base/*` → `/ai/llm-base/*`（4 处）；**删除死代码** `/ai/chat/sessions*` 5 个函数（后端无此路由） |
| `ai/model_config.ts` | 6 处 prefix → `/ai/model-configs` |
| `ai/ocr.ts` | `/ai/ocr/lang` → `/languages` |
| `authorization/auth.ts` | `/auth/me_id|me_permissions` → kebab |
| `authorization/casbin.ts` | 17 处 `/authorization/casbin_rules` → `/casbin-rules` |
| `authorization/role.ts` | `/roles/list_all` → `/roles/all` |
| `file/filesystem.ts` | list-dir / entries / files / folders / list-by-path / mkdir-p（6 处） |
| `life/baby_name.ts` | fetchEventSource URL → `/life/baby-names/predict-baby-info-base` |
| `little_utils/todolist.ts` | 6 处 → `/todolists` |
| `main/dict.ts` | by-type / by-type/.../count（2 处） |
| `main/status.ts` | 5 处 → `/server-status/*` kebab |
| `rag/document.ts` | `/reparse_task` → `/reparse-task` |

### 验证
```
cd code\frontend\vue3 && pnpm type-check && pnpm build
```

---

## 阶段③：后端函数名统一 + 注释补全（~40 个文件，去重）

### 3.1 list 系列统一（核心改名）
**规则：`list_all()`=全量、`list_paged(pagination)`=分页**

改名 A — `list_all(pagination...)` → `list_paged(...)`：13 组 dao+service（authorization/user、role、permission；template；rag/project；ai/model_config；nlp/synonym 含 `list_all_by_pid`→`list_paged_by_pid`；main/dict_type、dict_item；little_utils/todolist；life/baby_name；geometry/feature；dev_tools/template_string；file/filesystem）+ 对应 controller 调用点与 handler 名（如 role 的 `list_all` → `list_roles`）。

改名 B — `list_all_no_page`/`list_all_without_page` → `list_all()`：role（dao/service/controller handler `list_all_no_page`→`list_all_roles`）、permission（dao，service 内部调用点）、geometry/feature（dao/service）。

保持不动：dept 的 `list_all`（已是全量语义）、module_task 的 `list_page` 系列。

### 3.2 其他命名修正
- `itnfinite_scroll_response` 拼写错误（module_template/controller/template.py、module_little_utils/controller/todolist.py）
- module_main/dao/dict_item.py `get_by_code(dict_type_id, item_code)` → `get_by_type_and_code`
- module_ai/controller/ocr.py `tupu` → `segment_layout`、函数 `ocr` → `recognize`（随 URL 同步）
- module_ai/controller/translate.py `base`/`ocr` → `translate_base`/`translate_ocr`
- module_authorization/controller/auth.py `read_users_me`/`read_users_me_id`/`read_user_permissions` → `get_me`/`get_me_id`/`get_my_permissions`
- module_office/controller/document_chunk.py 空路由：删除空文件并在 app.py 说明

测试不受函数改名影响（已核查：tests 仅 HTTP 调用）。

### 3.3 注释补全（中文）
- controller/service 层缺失 docstring 的公共方法（统计：module_ai 22、module_file 20、module_rag 18、module_template 17、module_main 13、little_utils 7、office 5、geometry 4，其余零星）
- dao 层关键方法 + common/utils 公共设施（db session、token_util、pagination 等）
- 注释风格：一句话说明用途 + 关键参数，与现有 DaoRel 方法注释风格一致

### 验证
```
.venv\Scripts\python.exe -m pytest tests -q   # 全绿
```

---

## 阶段④：前端函数名统一 + 注释补全（~20 个文件）

### 4.1 api 函数改名（7 个 api 文件 + ~8 个调用方 .vue）
- rag/member.ts：`addProjectMember`→`createProjectMember`、`removeProjectMember`→`deleteProjectMember`
- rag/deptAuth.ts：`addProjectDept`→`createProjectDept`、`removeProjectDept`→`deleteProjectDept`
- authorization/casbin.ts：`addPolicy`→`createPolicy`、`removePolicy`→`deletePolicy`、`addRoleForUser`→`createRoleForUser`、`removeRoleForUser`→`deleteRoleForUser`
- ai/ocr.ts：`fetchLanguages`→`getLanguages`
- 3 处 `infiniteScrollXxx` → `scrollXxx`（model_config/todolist/template）
- 修正 todolist.ts/template.ts 中错写为"模板"的 JSDoc

命名规则：CRUD 用 `create/get/list/update/delete`；全量 `listAllXxx`；滚动 `scrollXxx`；动作端点保留业务动词。

### 4.2 注释补全
- stores（auth/sys/router）补 state/action 级注释
- pages 重点页面 ~15 个：文件头功能注释 + `<script setup>` 内关键函数注释（overview.vue 等零注释页面优先）
- common/components（chat 系列等）补 props/emits 说明
- geometry/utils/EarthScene.ts 等工具类补类与方法注释

### 验证
```
pnpm type-check && pnpm build   # 零错误
```

---

## 阶段⑤：全量回归

1. 后端：`python -m pytest tests -q` 全绿（154+）
2. 前端：`pnpm type-check && pnpm build` 零错误
3. 对比阶段①的 openapi.json 快照确认路由变更完整
4. 手工核心链路冒烟（启动后端 + Celery worker + 前端 dev）：登录 → Swagger Authorize（验证 tokenUrl）→ 字典管理 → 文件上传/下载（**local 与对象存储两种 storage_type 各测一次预签名链路**，最高风险点）→ 权限管理 → 任务队列 → 监控页

---

## 关键风险点

1. **预签名派生逻辑**（`src/module_file/service/filesystem.py` L877/L945）：字符串耦合路径名，必须用常量直传方案，且双 storage_type 验证
2. **OAuth2 tokenUrl**（`src/module_authorization/dependencies/auth.py` L11）：`/_token` 改名漏改会导致 Swagger Authorize 静默失效
3. **`ai/chat.ts` 死代码**（`/ai/chat/sessions*`）：删除前 grep 确认无页面引用
4. 前后端改名需在同一发布窗口内完成（后端先、前端紧随），避免线上 404

## 执行约定

- 注释一律中文；遵循用户规则（Python 3.13 新语法类型标注）
- 每阶段完成即运行对应验证命令，全绿后进入下一阶段
- 不新增文档文件（用户未要求）；现有 README/dir.md 等如引用旧 URL 则同步更新
