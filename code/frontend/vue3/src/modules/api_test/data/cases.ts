/**
 * 前端接口测试用例清单
 *
 * 收录前端全部业务接口(与 src/modules/<模块>/api/ 下的文件一一对应):
 * - fn/file 用于与 api 模块导出函数做覆盖校验(页面会提示未收录的函数, 防止清单漂移)
 * - auto 自动推导: GET 且无路径参数且未跳过 → 参与"全部执行"; 其余(有副作用/需资源ID)仅单条执行
 * - skip: 后端模块未启用(app.py 注释待启用)或 SSE/WebSocket 非普通 HTTP 接口
 * - allow404: 资源型接口(需真实ID), 404 视为"路由可达"警告而非契约断裂
 */

/** HTTP 方法 */
export type ApiMethod = 'GET' | 'POST' | 'PUT' | 'DELETE';

/** 接口测试用例定义 */
export interface ApiCase {
  /** 所属前端模块(分组显示) */
  module: string;
  /** 对应 api 文件名(覆盖校验用) */
  file: string;
  /** 对应 api 模块导出函数名(覆盖校验用) */
  fn: string;
  method: ApiMethod;
  /** 接口路径, 路径参数用 {x} 占位(执行时替换为 0) */
  path: string;
  /** 是否参与"全部执行"(缺省按 GET 且无路径参数自动推导) */
  auto?: boolean;
  /** 资源型接口: 404 视为路由可达(警告)而非契约断裂 */
  allow404?: boolean;
  /** 跳过执行(后端未启用/SSE/WebSocket) */
  skip?: boolean;
  /** 备注(风险提示/参数要求等) */
  note?: string;
}

/** 紧凑构造器 */
const c = (
  module: string,
  file: string,
  fn: string,
  method: ApiMethod,
  path: string,
  opts: Partial<ApiCase> = {},
): ApiCase => ({ module, file, fn, method, path, ...opts });

export const API_CASES: ApiCase[] = [
  // ==================== AI 服务 ====================
  // 模型配置(已挂载)
  c('ai', 'model_config.ts', 'listModelConfigs', 'GET', '/ai/model-configs/list'),
  c('ai', 'model_config.ts', 'infiniteScrollModelConfigs', 'GET', '/ai/model-configs/scroll'),
  c('ai', 'model_config.ts', 'getModelConfig', 'GET', '/ai/model-configs/{modelId}', { allow404: true, note: '需真实模型ID' }),
  c('ai', 'model_config.ts', 'createModelConfig', 'POST', '/ai/model-configs', { note: '创建模型配置' }),
  c('ai', 'model_config.ts', 'updateModelConfig', 'PUT', '/ai/model-configs/{modelId}', { allow404: true }),
  c('ai', 'model_config.ts', 'deleteModelConfig', 'DELETE', '/ai/model-configs/{modelId}', { allow404: true }),
  c('ai', 'model_config.ts', 'revectorizeChunks', 'POST', '/rag/project-document-chunks/revectorize', { note: '触发全库重向量化任务, 慎用' }),
  c('ai', 'model_config.ts', 'getRevectorizeStatus', 'GET', '/rag/project-document-chunks/revectorize/status/{taskId}', { allow404: true }),
  // LLM 对话(真实 LLM 调用, 不自动执行)
  c('ai', 'chat.ts', 'sendChatMessage', 'POST', '/ai/llm/chat', { skip: true, note: '真实调用 LLM, 仅手动验证' }),
  c('ai', 'chat.ts', 'sendChatMessageStream', 'POST', '/ai/llm/chat', { skip: true, note: 'SSE 流式 + 真实调用 LLM, 仅手动验证' }),
  c('ai', 'chat.ts', 'clearModelCache', 'DELETE', '/ai/llm/cache/{modelId}', { note: '写操作(清空模型实例缓存), 手动执行' }),
  c('ai', 'chat.ts', 'checkModelConfig', 'POST', '/ai/llm/check-config', { skip: true, note: '真实调用模型校验, 仅手动验证' }),
  // OCR(需图片文件, 手动验证)
  c('ai', 'ocr.ts', 'listOcrLanguages', 'GET', '/ai/ocr/languages'),
  c('ai', 'ocr.ts', 'recognizeText', 'POST', '/ai/ocr/all', { skip: true, note: '需图片文件, 手动验证' }),
  // 语音(需音频/文本参数, 手动验证)
  c('ai', 'voice.ts', 'recognizeAudio', 'POST', '/ai/voice/asr', { skip: true, note: '需音频文件, 手动验证' }),
  c('ai', 'voice.ts', 'synthesizeAudioFile', 'POST', '/ai/voice/tts/file', { skip: true, note: '真实调用 TTS 模型, 手动验证' }),
  c('ai', 'voice.ts', 'synthesizeAudioStream', 'POST', '/ai/voice/tts/stream', { skip: true, note: '流式 PCM + 真实调用 TTS 模型, 手动验证' }),
  c('ai', 'voice.ts', 'buildAsrStreamUrl', 'GET', '/ai/voice/asr/stream', { skip: true, note: 'WebSocket 接口, 手动验证' }),

  // ==================== 权限管理 ====================
  // 认证
  c('authorization', 'auth.ts', 'registerUser', 'POST', '/authorization/auth/register', { note: '注册用户' }),
  c('authorization', 'auth.ts', 'loginUser', 'POST', '/authorization/auth/login', { note: 'OAuth2 表单登录' }),
  c('authorization', 'auth.ts', 'logoutUser', 'POST', '/authorization/auth/logout', { note: '注销当前令牌' }),
  c('authorization', 'auth.ts', 'refreshToken', 'POST', '/authorization/auth/refresh', { note: '刷新令牌' }),
  c('authorization', 'auth.ts', 'getCurrentUser', 'GET', '/authorization/auth/me'),
  c('authorization', 'auth.ts', 'getCurrentUserId', 'GET', '/authorization/auth/me-id'),
  c('authorization', 'auth.ts', 'getUserPermissions', 'GET', '/authorization/auth/me-permissions'),
  c('authorization', 'auth.ts', 'updateMyProfile', 'PUT', '/authorization/auth/me', { note: '自助更新个人资料' }),
  c('authorization', 'auth.ts', 'changeMyPassword', 'PUT', '/authorization/auth/me/password', { note: '自助修改密码(需旧密码)' }),
  c('authorization', 'auth.ts', 'uploadMyAvatar', 'POST', '/authorization/auth/me/avatar', { note: '上传当前用户头像(需图片文件, 经统一文件服务存储)' }),
  // 用户
  c('authorization', 'user.ts', 'createUser', 'POST', '/authorization/users', { note: '创建用户' }),
  c('authorization', 'user.ts', 'deleteUser', 'DELETE', '/authorization/users/{userId}', { allow404: true }),
  c('authorization', 'user.ts', 'updateUser', 'PUT', '/authorization/users/{userId}', { allow404: true }),
  c('authorization', 'user.ts', 'getUser', 'GET', '/authorization/users/{userId}', { allow404: true }),
  c('authorization', 'user.ts', 'listUsers', 'GET', '/authorization/users/list'),
  c('authorization', 'user.ts', 'authenticateUser', 'POST', '/authorization/users/authenticate', { note: '校验用户名密码' }),
  // 角色
  c('authorization', 'role.ts', 'createRole', 'POST', '/authorization/roles', { note: '创建角色' }),
  c('authorization', 'role.ts', 'updateRole', 'PUT', '/authorization/roles/{roleId}', { allow404: true }),
  c('authorization', 'role.ts', 'deleteRole', 'DELETE', '/authorization/roles/{roleId}', { allow404: true }),
  c('authorization', 'role.ts', 'getRole', 'GET', '/authorization/roles/{roleId}', { allow404: true }),
  c('authorization', 'role.ts', 'listRoles', 'GET', '/authorization/roles/list'),
  c('authorization', 'role.ts', 'listAllRoles', 'GET', '/authorization/roles/all'),
  c('authorization', 'role.ts', 'getRoleByName', 'GET', '/authorization/roles/name/{name}', { allow404: true }),
  c('authorization', 'role.ts', 'getRoleByKey', 'GET', '/authorization/roles/key/{roleKey}', { allow404: true }),
  // 权限
  c('authorization', 'permission.ts', 'createPermission', 'POST', '/authorization/permissions', { note: '创建权限' }),
  c('authorization', 'permission.ts', 'updatePermission', 'PUT', '/authorization/permissions/{permissionId}', { allow404: true }),
  c('authorization', 'permission.ts', 'deletePermission', 'DELETE', '/authorization/permissions/{permissionId}', { allow404: true }),
  c('authorization', 'permission.ts', 'getPermission', 'GET', '/authorization/permissions/{permissionId}', { allow404: true }),
  c('authorization', 'permission.ts', 'listPermissions', 'GET', '/authorization/permissions/list'),
  c('authorization', 'permission.ts', 'getPermissionTree', 'GET', '/authorization/permissions/tree'),
  c('authorization', 'permission.ts', 'getPermissionByCode', 'GET', '/authorization/permissions/code/{code}', { allow404: true }),
  c('authorization', 'permission.ts', 'getPermissionsByParentId', 'GET', '/authorization/permissions/parent/{parentId}', { allow404: true }),
  // 部门
  c('authorization', 'dept.ts', 'getDeptTree', 'GET', '/authorization/depts/tree'),
  c('authorization', 'dept.ts', 'listDepts', 'GET', '/authorization/depts/list'),
  c('authorization', 'dept.ts', 'getDept', 'GET', '/authorization/depts/{deptId}', { allow404: true }),
  c('authorization', 'dept.ts', 'createDept', 'POST', '/authorization/depts', { note: '创建部门' }),
  c('authorization', 'dept.ts', 'updateDept', 'PUT', '/authorization/depts/{deptId}', { allow404: true }),
  c('authorization', 'dept.ts', 'deleteDept', 'DELETE', '/authorization/depts/{deptId}', { allow404: true }),
  // Casbin 策略
  c('authorization', 'casbin.ts', 'addRoleForUser', 'POST', '/authorization/casbin-rules/role-user', { note: '写入授权' }),
  c('authorization', 'casbin.ts', 'removeRoleForUser', 'DELETE', '/authorization/casbin-rules/role-user', { note: '移除授权' }),
  c('authorization', 'casbin.ts', 'getRolesForUser', 'GET', '/authorization/casbin-rules/roles/{userId}', { allow404: true }),
  c('authorization', 'casbin.ts', 'getPermissionsForRole', 'GET', '/authorization/casbin-rules/permissions/{roleKey}', { allow404: true }),
  c('authorization', 'casbin.ts', 'checkPermission', 'POST', '/authorization/casbin-rules/check-permission', { note: '权限校验' }),
  c('authorization', 'casbin.ts', 'batchAddRolePermissions', 'POST', '/authorization/casbin-rules/batch-role-permissions', { note: '批量写入' }),
  c('authorization', 'casbin.ts', 'batchAddUserRoles', 'POST', '/authorization/casbin-rules/batch-user-roles', { note: '批量写入' }),
  c('authorization', 'casbin.ts', 'deleteRolePermissions', 'DELETE', '/authorization/casbin-rules/role-permissions/{roleKey}', { note: '清空角色授权' }),
  c('authorization', 'casbin.ts', 'deleteUserRoles', 'DELETE', '/authorization/casbin-rules/user-roles/{userId}', { note: '清空用户角色' }),
  c('authorization', 'casbin.ts', 'reloadPolicy', 'POST', '/authorization/casbin-rules/reload-policy', { note: '重载策略' }),
  c('authorization', 'casbin.ts', 'getAllPolicies', 'GET', '/authorization/casbin-rules/policies'),
  c('authorization', 'casbin.ts', 'getAllGroupingPolicies', 'GET', '/authorization/casbin-rules/grouping-policies'),
  c('authorization', 'casbin.ts', 'addPolicy', 'POST', '/authorization/casbin-rules/policy', { note: '写入策略' }),
  c('authorization', 'casbin.ts', 'removePolicy', 'DELETE', '/authorization/casbin-rules/policy', { note: '删除策略' }),
  c('authorization', 'casbin.ts', 'getModuleTree', 'GET', '/authorization/casbin-rules/module-tree'),
  c('authorization', 'casbin.ts', 'getRolePermCodes', 'GET', '/authorization/casbin-rules/role-perms/{roleKey}', { allow404: true }),
  c('authorization', 'casbin.ts', 'syncRolePermissions', 'POST', '/authorization/casbin-rules/role-perms', { note: '覆盖式同步角色权限' }),

  // ==================== 数据清洗 ====================
  c('data_clean', 'data_clean.ts', 'cleanData', 'POST', '/data-clean/clean', { note: 'LLM 调用, 需文本与清洗方案' }),

  // ==================== 文件管理 ====================
  c('file', 'filesystem.ts', 'getUploadMode', 'GET', '/file/filesystem/upload-mode'),
  c('file', 'filesystem.ts', 'listDir', 'GET', '/file/filesystem/list-dir'),
  c('file', 'filesystem.ts', 'listDirs', 'GET', '/file/filesystem/dirs'),
  c('file', 'filesystem.ts', 'uploadFile', 'POST', '/file/filesystem/multipart/init', { note: '分片上传(由 uploadFile 内部调用)' }),
  c('file', 'filesystem.ts', 'uploadFile', 'PUT', '/file/filesystem/multipart/{uploadId}/parts/{partNumber}', { allow404: true, note: '分片上传(由 uploadFile 内部调用)' }),
  c('file', 'filesystem.ts', 'uploadFile', 'POST', '/file/filesystem/multipart/{uploadId}/complete', { allow404: true, note: '分片上传(由 uploadFile 内部调用)' }),
  c('file', 'filesystem.ts', 'uploadFile', 'POST', '/file/filesystem/upload-complete', { note: '直传完成确认(由 uploadFile 内部调用)' }),
  c('file', 'filesystem.ts', 'uploadFile', 'POST', '/file/filesystem/upload', { note: '直传, 需文件' }),
  c('file', 'filesystem.ts', 'createFolder', 'POST', '/file/filesystem/folder', { note: '新建文件夹' }),
  c('file', 'filesystem.ts', 'getFileEntry', 'GET', '/file/filesystem/entries/{entryId}', { allow404: true }),
  c('file', 'filesystem.ts', 'getFileDownloadUrl', 'GET', '/file/filesystem/download/{entryId}', { allow404: true, note: '文件流下载' }),
  c('file', 'filesystem.ts', 'updateFileEntry', 'PUT', '/file/filesystem/entries/{entryId}', { allow404: true }),
  c('file', 'filesystem.ts', 'renameEntry', 'PUT', '/file/filesystem/entries/{entryId}/rename', { allow404: true }),
  c('file', 'filesystem.ts', 'moveEntry', 'PUT', '/file/filesystem/entries/{entryId}/move', { allow404: true }),
  c('file', 'filesystem.ts', 'deleteFile', 'DELETE', '/file/filesystem/files/{entryId}', { allow404: true }),
  c('file', 'filesystem.ts', 'deleteFolder', 'DELETE', '/file/filesystem/folders/{folderId}', { allow404: true }),
  c('file', 'filesystem.ts', 'getEntryByPath', 'GET', '/file/filesystem/path', { note: '需 path 查询参数' }),
  c('file', 'filesystem.ts', 'listByPath', 'GET', '/file/filesystem/list-by-path', { note: '需 path 查询参数' }),
  c('file', 'filesystem.ts', 'mkdirP', 'POST', '/file/filesystem/mkdir-p', { note: '需 path 参数' }),
  c('file', 'filesystem.ts', 'searchEntries', 'GET', '/file/filesystem/search', { note: '需 keyword 查询参数' }),
  c('file', 'filesystem.ts', 'copyEntry', 'POST', '/file/filesystem/copy', { note: '复制条目' }),
  c('file', 'filesystem.ts', 'getStorageStats', 'GET', '/file/filesystem/stats'),
  c('file', 'filesystem.ts', 'migrateStorage', 'POST', '/file/filesystem/migrate', { note: '存储迁移(可续传), 慎用' }),

  // ==================== 地理空间 ====================
  c('geometry', 'feature.ts', 'listGeoFeatures', 'GET', '/geometry/features/list'),
  c('geometry', 'feature.ts', 'listAllGeoFeatures', 'GET', '/geometry/features/all'),
  c('geometry', 'feature.ts', 'getGeoFeature', 'GET', '/geometry/features/{featureId}', { allow404: true }),
  c('geometry', 'feature.ts', 'createGeoFeature', 'POST', '/geometry/features', { note: '创建要素' }),
  c('geometry', 'feature.ts', 'updateGeoFeature', 'PUT', '/geometry/features/{featureId}', { allow404: true }),
  c('geometry', 'feature.ts', 'deleteGeoFeature', 'DELETE', '/geometry/features/{featureId}', { allow404: true }),

  // ==================== 生活工具(后端模块未启用) ====================
  c('life', 'baby_name.ts', 'predictBabyNameStream', 'POST', '/life/baby-names/predict-baby-info-base', { skip: true, note: 'SSE 流式, 后端模块未启用' }),

  // ==================== 个人小站(博客/备忘/记账 三条业务线) ====================
  // 博客(markdown 在线编辑 / 关联 URL 发布展示)
  c('site', 'blog.ts', 'listPublishedPosts', 'GET', '/site/blog/posts/view/list'),
  c('site', 'blog.ts', 'listMyPosts', 'GET', '/site/blog/posts/list'),
  c('site', 'blog.ts', 'getBlogPost', 'GET', '/site/blog/posts/{postId}', { allow404: true }),
  c('site', 'blog.ts', 'createBlogPost', 'POST', '/site/blog/posts', { note: '发布文章' }),
  c('site', 'blog.ts', 'updateBlogPost', 'PUT', '/site/blog/posts/{postId}', { allow404: true }),
  c('site', 'blog.ts', 'deleteBlogPost', 'DELETE', '/site/blog/posts/{postId}', { allow404: true }),
  // 备忘(编辑管理 + 日历 年/月/周 展示数据源)
  c('site', 'todolist.ts', 'listTodolists', 'GET', '/site/todolists/list'),
  c('site', 'todolist.ts', 'listMemosByRange', 'GET', '/site/todolists/range', { auto: false, note: '需 start/end 查询参数' }),
  c('site', 'todolist.ts', 'getTodolist', 'GET', '/site/todolists/{todolistId}', { allow404: true }),
  c('site', 'todolist.ts', 'createTodolist', 'POST', '/site/todolists', { note: '创建备忘' }),
  c('site', 'todolist.ts', 'updateTodolist', 'PUT', '/site/todolists/{todolistId}', { allow404: true }),
  c('site', 'todolist.ts', 'deleteTodolist', 'DELETE', '/site/todolists/{todolistId}', { allow404: true }),
  // 记账本(收支记录 + 月度图表统计)
  c('site', 'ledger.ts', 'listLedgerRecords', 'GET', '/site/ledger/records/list'),
  c('site', 'ledger.ts', 'getLedgerStats', 'GET', '/site/ledger/records/stats', { auto: false, note: '需 month 查询参数(YYYY-MM)' }),
  c('site', 'ledger.ts', 'getLedgerRecord', 'GET', '/site/ledger/records/{recordId}', { allow404: true }),
  c('site', 'ledger.ts', 'createLedgerRecord', 'POST', '/site/ledger/records', { note: '记一笔' }),
  c('site', 'ledger.ts', 'updateLedgerRecord', 'PUT', '/site/ledger/records/{recordId}', { allow404: true }),
  c('site', 'ledger.ts', 'deleteLedgerRecord', 'DELETE', '/site/ledger/records/{recordId}', { allow404: true }),

  // ==================== 数据管理 ====================
  // 字典
  c('main', 'dict.ts', 'createDictType', 'POST', '/dict_types', { note: '创建字典类型' }),
  c('main', 'dict.ts', 'listDictTypes', 'GET', '/dict_types/list'),
  c('main', 'dict.ts', 'getDictTypeByCode', 'GET', '/dict_types/code/{typeCode}', { allow404: true }),
  c('main', 'dict.ts', 'getDictType', 'GET', '/dict_types/{typeId}', { allow404: true }),
  c('main', 'dict.ts', 'updateDictType', 'PUT', '/dict_types/{typeId}', { allow404: true }),
  c('main', 'dict.ts', 'deleteDictType', 'DELETE', '/dict_types/{typeId}', { allow404: true }),
  c('main', 'dict.ts', 'createDictItem', 'POST', '/dict_items', { note: '创建字典项' }),
  c('main', 'dict.ts', 'listDictItems', 'GET', '/dict_items/list'),
  c('main', 'dict.ts', 'listDictItemsByType', 'GET', '/dict_items/by-type/{typeCode}', { allow404: true }),
  c('main', 'dict.ts', 'countDictItemsByType', 'GET', '/dict_items/by-type/{typeCode}/count', { allow404: true }),
  c('main', 'dict.ts', 'getDictItemByCode', 'GET', '/dict_items/code/{itemCode}', { allow404: true }),
  c('main', 'dict.ts', 'getDictItem', 'GET', '/dict_items/{itemId}', { allow404: true }),
  c('main', 'dict.ts', 'updateDictItem', 'PUT', '/dict_items/{itemId}', { allow404: true }),
  c('main', 'dict.ts', 'deleteDictItem', 'DELETE', '/dict_items/{itemId}', { allow404: true }),
  // 服务器状态
  c('main', 'status.ts', 'getStatusCache', 'GET', '/server-status/cache'),
  c('main', 'status.ts', 'getSysInfo', 'GET', '/server-status/sys-info'),
  c('main', 'status.ts', 'getHardwareStatus', 'GET', '/server-status/hardware-status'),
  c('main', 'status.ts', 'getNetworkStatus', 'GET', '/server-status/network-status'),
  c('main', 'status.ts', 'getMountCount', 'GET', '/server-status/mount-count'),

  // ==================== 知识库 ====================
  // 项目
  c('rag', 'project.ts', 'createRagProject', 'POST', '/rag/projects', { note: '创建项目' }),
  c('rag', 'project.ts', 'listRagProjects', 'GET', '/rag/projects/list'),
  c('rag', 'project.ts', 'getRagProject', 'GET', '/rag/projects/{projectId}', { allow404: true }),
  c('rag', 'project.ts', 'updateRagProject', 'PUT', '/rag/projects/{projectId}', { allow404: true }),
  c('rag', 'project.ts', 'deleteRagProject', 'DELETE', '/rag/projects/{projectId}', { allow404: true }),
  // 成员
  c('rag', 'member.ts', 'addProjectMember', 'POST', '/rag/project-members', { note: '添加成员' }),
  c('rag', 'member.ts', 'listMyProjects', 'GET', '/rag/project-members/my'),
  c('rag', 'member.ts', 'listProjectMembers', 'GET', '/rag/project-members/project/{projectId}', { allow404: true }),
  c('rag', 'member.ts', 'getProjectMember', 'GET', '/rag/project-members/{memberId}', { allow404: true }),
  c('rag', 'member.ts', 'removeProjectMember', 'DELETE', '/rag/project-members/{memberId}', { allow404: true }),
  c('rag', 'member.ts', 'updateProjectMember', 'PUT', '/rag/project-members/{memberId}', { allow404: true }),
  // 文档
  c('rag', 'document.ts', 'uploadRagDocument', 'POST', '/rag/project-documents/{projectId}/upload', { allow404: true, note: '需项目ID与文件' }),
  c('rag', 'document.ts', 'listRagProjectDocuments', 'GET', '/rag/project-documents/{projectId}/list', { allow404: true, note: '需真实项目ID' }),
  c('rag', 'document.ts', 'getRagDocument', 'GET', '/rag/project-documents/{documentId}', { allow404: true }),
  c('rag', 'document.ts', 'getRagDocumentIngestProgress', 'GET', '/rag/project-documents/{documentId}/progress', { allow404: true }),
  c('rag', 'document.ts', 'getRagDocumentDownloadUrl', 'GET', '/rag/project-documents/{documentId}/download', { allow404: true }),
  c('rag', 'document.ts', 'updateRagDocument', 'PUT', '/rag/project-documents/{documentId}', { allow404: true }),
  c('rag', 'document.ts', 'deleteRagDocument', 'DELETE', '/rag/project-documents/{documentId}', { allow404: true }),
  c('rag', 'document.ts', 'reparseRagDocument', 'POST', '/rag/project-documents/{documentId}/reparse', { allow404: true, note: '触发重新解析' }),
  c('rag', 'document.ts', 'reparseRagDocumentTask', 'POST', '/rag/project-documents/{documentId}/reparse-task', { allow404: true, note: '触发异步重新解析' }),
  c('rag', 'document.ts', 'getSupportedFileTypes', 'GET', '/rag/project-documents/supported-types'),
  c('rag', 'document.ts', 'getRagUploadMode', 'GET', '/rag/project-documents/upload-mode'),
  c('rag', 'document.ts', 'checkRagParseModels', 'GET', '/rag/project-documents/model-check'),
  c('rag', 'document.ts', 'listRagEntries', 'GET', '/rag/project-documents/{projectId}/entries', { allow404: true, note: '条目级浏览(目录+文件), 需真实项目ID' }),
  c('rag', 'document.ts', 'createRagFolder', 'POST', '/rag/project-documents/{projectId}/folders', { allow404: true, note: '项目内创建文件夹(名称query)' }),
  c('rag', 'document.ts', 'renameRagFolder', 'PUT', '/rag/project-documents/{projectId}/folders/{folderId}', { allow404: true }),
  c('rag', 'document.ts', 'deleteRagFolder', 'DELETE', '/rag/project-documents/{projectId}/folders/{folderId}', { allow404: true, note: '递归删除项目内文件夹' }),
  // 部门授权
  c('rag', 'deptAuth.ts', 'addProjectDept', 'POST', '/rag/project-depts', { note: '写入部门授权' }),
  c('rag', 'deptAuth.ts', 'getAuthDeptTree', 'GET', '/rag/project-depts/dept-tree'),
  c('rag', 'deptAuth.ts', 'listProjectDepts', 'GET', '/rag/project-depts/project/{projectId}', { allow404: true }),
  c('rag', 'deptAuth.ts', 'updateProjectDept', 'PUT', '/rag/project-depts/{id}', { allow404: true }),
  c('rag', 'deptAuth.ts', 'removeProjectDept', 'DELETE', '/rag/project-depts/{id}', { allow404: true }),
  // 用户模型绑定(v4 4.3: 绑定校验归属, 回退开关)
  c('rag', 'user_model.ts', 'getMyModelBinding', 'GET', '/rag/user-models/my'),
  c('rag', 'user_model.ts', 'updateMyModelBinding', 'PUT', '/rag/user-models/my', { note: '仅可绑定公共/本部门/自己的模型' }),
  // 会话与问答
  c('rag', 'conversation.ts', 'createConversation', 'POST', '/rag/conversations', { note: '创建会话' }),
  c('rag', 'conversation.ts', 'listMyConversations', 'GET', '/rag/conversations/my'),
  c('rag', 'conversation.ts', 'getConversation', 'GET', '/rag/conversations/{conversationId}', { allow404: true }),
  c('rag', 'conversation.ts', 'updateConversation', 'PUT', '/rag/conversations/{conversationId}', { allow404: true }),
  c('rag', 'conversation.ts', 'deleteConversation', 'DELETE', '/rag/conversations/{conversationId}', { allow404: true }),
  c('rag', 'conversation.ts', 'listConversationMessages', 'GET', '/rag/conversations/{conversationId}/messages', { allow404: true }),
  c('rag', 'conversation.ts', 'summarizeConversation', 'POST', '/rag/rag-chat/{conversationId}/summarize', { allow404: true, note: 'LLM 调用' }),
  c('rag', 'conversation.ts', 'sendRagChatStream', 'POST', '/rag/rag-chat/{conversationId}/chat', { skip: true, note: 'SSE 流式, 请在问答页测试' }),

  // ==================== 任务队列 ====================
  c('task', 'task.ts', 'getTaskRegistry', 'GET', '/task/tasks/registry'),
  c('task', 'task.ts', 'getTaskStats', 'GET', '/task/tasks/stats'),
  c('task', 'task.ts', 'listTasks', 'GET', '/task/tasks/list'),
  c('task', 'task.ts', 'getTask', 'GET', '/task/tasks/{id}', { allow404: true }),
  c('task', 'task.ts', 'createTask', 'POST', '/task/tasks', { note: '提交任务' }),
  c('task', 'task.ts', 'syncTask', 'POST', '/task/tasks/{id}/sync', { allow404: true }),
  c('task', 'task.ts', 'cancelTask', 'POST', '/task/tasks/{id}/cancel', { allow404: true }),
  c('task', 'task.ts', 'retryTask', 'POST', '/task/tasks/{id}/retry', { allow404: true }),
  c('task', 'task.ts', 'deleteTask', 'DELETE', '/task/tasks/{id}', { allow404: true }),

  // ==================== 模板示例(后端模块未启用) ====================
  c('template', 'template.ts', 'createTemplate', 'POST', '/template/templates', { skip: true, note: '后端模块未启用' }),
  c('template', 'template.ts', 'deleteTemplate', 'DELETE', '/template/templates/{id}', { skip: true, note: '后端模块未启用' }),
  c('template', 'template.ts', 'updateTemplate', 'PUT', '/template/templates/{id}', { skip: true, note: '后端模块未启用' }),
  c('template', 'template.ts', 'getTemplate', 'GET', '/template/templates/{id}', { skip: true, note: '后端模块未启用' }),
  c('template', 'template.ts', 'listTemplates', 'GET', '/template/templates/list', { skip: true, note: '后端模块未启用' }),
  c('template', 'template.ts', 'infiniteScrollTemplates', 'GET', '/template/templates/scroll', { skip: true, note: '后端模块未启用' }),
  // 人脸特征(纯前端函数, 非 HTTP 接口, 仅做覆盖登记)
  c('template', 'face.ts', 'extractFaceFeature', 'GET', '/template/face/feature', { skip: true, note: '纯前端函数: 从 blendshapes 提取标准化特征向量' }),
  c('template', 'face.ts', 'normalizeVector', 'GET', '/template/face/feature', { skip: true, note: '纯前端函数: 向量 L2 归一化' }),
  c('template', 'face.ts', 'cosineSimilarity', 'GET', '/template/face/compare', { skip: true, note: '纯前端函数: 两向量余弦相似度' }),
  c('template', 'face.ts', 'compareFaceFeatures', 'GET', '/template/face/compare', { skip: true, note: '纯前端函数: 特征比较(相似度+阈值判定)' }),
];

/** 用例唯一键 */
export function caseKey(c: ApiCase): string {
  return `${c.method}:${c.path}:${c.fn}`;
}

/**
 * 是否自动执行: GET 且无路径参数且未跳过
 * (带路径参数的依赖真实资源, 写操作有副作用, 均只支持单条执行)
 */
export function isAutoCase(c: ApiCase): boolean {
  if (c.auto !== undefined) return c.auto;
  return c.method === 'GET' && !c.path.includes('{') && !c.skip;
}
