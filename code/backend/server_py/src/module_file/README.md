# module_file 网络文件系统模块

完整的网络文件系统（虚拟文件树 + 可切换物理存储），支持 `local` / `rustfs` / `s3`(MinIO等) 三种存储的**无缝切换**，对所有调用方（前端 / 其他后端模块）暴露**完全一致**的接口。

## 1. 架构

```
前端(Vue3) / 其他模块(FileClient)
        │  统一 REST 接口 (/file/filesystem/*)
        ▼
controller/filesystem.py ──► service/filesystem.py (FileService)
        │                          │
        │                          ├── dao/file_entry_dao.py    虚拟文件树(条目: 文件+目录, pid树, 逻辑路径)
        │                          ├── dao/file_content_dao.py  物理内容(内容哈希去重, 引用计数)
        │                          ▼
        │                  StorageInterface(存储抽象)
        │                          ├── storage_local.py  本地磁盘(aiofiles + HMAC签名代理)
        │                          └── storage_s3.py     S3协议(rustfs/minio/oss, aioboto3直传)
        ▼
config/filesystem.py: 按 conf.file_system.storage_type 启动时构建全局存储单例
```

核心设计：

- **虚拟文件树与物理存储解耦**：`file_entry` 表记录文件/目录树（pid + logical_path），`file_content` 表记录物理内容（content_hash 主键、physical_storage 物理键、storage_type 来源、ref_count 引用计数）。
- **内容哈希去重**：同一内容全系统仅存一份物理文件，复制/秒传零成本；引用计数归零自动清理物理文件。
- **存储无关**：业务层只见 `StorageInterface`（save/load/iter_chunks/delete/exists/size/list/presigned），切换存储不改一行业务代码。

## 2. 存储切换（local ↔ rustfs ↔ s3）

`config.dev.yaml`:

```yaml
file_system:
  storage_type: rustfs        # local | rustfs | s3 三选一
  max_size: 10                # 单文件上限(MB)
  allowed_extensions:         # MIME 白名单(支持 image/* 通配),空=不限制
    - "application/pdf"
    - "image/*"
  # rustfs / s3 / minio 共用以下 S3 协议配置(rustfs 完全兼容 S3)
  endpoint_url: "http://127.0.0.1:20004"
  access_key: "minioadmin"
  secret_key: "minioadmin"
  bucket: "bucket0"
  region: "us-east-1"
```

- `rustfs` 是 `s3` 的协议别名：配置类与实现类完全复用（[storage_config.py](utils/multi_storage/do/storage_config.py) 中注册别名），仅作为 `file_content.storage_type` 的来源标记。
- `local` 无需 S3 配置，默认落盘 `dir.base_child.upload` 目录（可用 `base_dir` 覆盖）。

### 无缝切换三步法（历史数据迁移）

1. **迁移物理内容**（不中断服务）：

   ```bash
   # 管理员 token 调用; from_type=当前实际存储, to_type=目标存储
   curl -X POST /file/filesystem/migrate \
        -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
        -d '{"from_type": "local", "to_type": "rustfs"}'
   # => {"total": n, "migrated": n1, "skipped": n2, "failed": [...]}
   # 支持断点续迁: 已在目标存储的记录自动跳过,失败项可重跑
   ```

2. **修改配置** `storage_type: rustfs`，重启服务。
3. 旧存储文件保留（回滚安全），确认稳定后手动清理。

> 注意：S3 直传（预签名）需要对象存储开启 CORS（允许 `PUT/GET` 与自定义查询参数头）。rustfs/minio 启动时配置即可。

## 3. REST 接口（前后端协议，与存储类型无关）

挂载前缀 `/file/filesystem`，权限码 `main:file:read/create/update/delete/migrate`。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/upload` | multipart 上传（流式后端代理，哈希去重秒传） |
| POST | `/folder?name=&pid=` | 创建目录 |
| POST | `/mkdir-p?path=/a/b/c` | 按路径递归创建目录（mkdir -p） |
| GET | `/list-dir?pid=&name=&page=&size=` | 按 pid 浏览目录（目录排前） |
| GET | `/list-by-path?path=/a/b` | 按逻辑路径浏览目录 |
| GET | `/path?path=/a/b/readme.md` | 按逻辑路径查询条目元数据 |
| GET | `/search?keyword=&page=&size=` | 全树模糊搜索（名称/路径） |
| GET | `/dirs?pid=` | 子目录列表（目录树懒加载） |
| GET | `/entries/{id}` | 条目元数据 |
| PUT | `/entries/{id}` | 更新描述/名称 |
| PUT | `/entries/{id}/rename?new_name=` | 重命名（目录同步子树路径） |
| PUT | `/entries/{id}/move?target_pid=` | 移动（环形防护） |
| POST | `/copy?entry_id=&target_pid=` | 复制（文件共享内容，目录递归整树） |
| GET | `/download/{id}` | 流式下载（后端代理） |
| DELETE | `/files/{id}` | 删除文件（引用计数-1，归零清物理） |
| DELETE | `/folders/{id}` | 递归删除目录 |
| GET | `/stats` | 统计（条目/内容/占用/当前存储类型） |
| POST | `/migrate` | 存储迁移（管理员） |

预签名直传三步协议（大文件绕过后端流量，前端只认"一个 URL"）：

| 步骤 | 接口 | 说明 |
|---|---|---|
| 1 | `POST /presigned/upload-url` | 传 filename/content_type/file_size_bytes/content_hash(SHA-256)，返回 `presigned_url`（local→后端代理完整URL；rustfs/s3→对象存储直传URL） |
| 2 | `PUT {presigned_url}` | 直接 PUT 文件体（签名即凭证，免 token） |
| 3 | `POST /presigned/upload-complete` | 通知建条目（FileEntryCreate） |

下载同理：`GET /presigned/download-url/{id}` 返回可直接 GET 的完整 URL。

## 4. 其他模块如何操作文件（增删改查）

### 方式一：模块级单例（推荐）

```python
from module_file.client import file_client

# —— 增 ——
entry = await file_client.upload_bytes(
    data_bytes, "report.pdf", path="/rag/docs", user_id=user_id)   # 目录不存在自动创建
entry = await file_client.save_text("hello", "note.txt", path="/notes")
folder = await file_client.mkdir("/rag/exports")                    # mkdir -p

# —— 删 ——
await file_client.remove(entry.id)              # 文件
await file_client.remove_tree(folder.id)        # 目录(递归)
await file_client.remove_by_path("/rag/docs")   # 按路径,自动判断文件/目录

# —— 改 ——
await file_client.rename(entry.id, "v2.pdf")
await file_client.move(entry.id, target_pid)
await file_client.move_to_path(entry.id, "/archive/2026")           # 目标目录自动创建
await file_client.copy(entry.id, target_pid)                        # 内容哈希去重,零物理复制
await file_client.set_description(entry.id, "季度报表")

# —— 查 ——
entry = await file_client.get(entry.id)
entry = await file_client.get_by_path("/rag/docs/report.pdf")
page = await file_client.list_dir(pid)          # items: list[FileEntry]
page = await file_client.list_by_path("/rag/docs")
page = await file_client.search("report")
data: bytes = await file_client.read_bytes(entry.id)
text: str  = await file_client.read_text(entry.id)
async for chunk in file_client.iter_file(entry.id):   # 大文件流式
    ...
stats = await file_client.stats()               # 占用统计

# —— 底层直连(不建虚拟条目,仅临时文件场景) ——
await file_client.storage.save("tmp/x.bin", b"...")
data = await file_client.storage.load("tmp/x.bin")
```

### 方式二：FastAPI 依赖注入（在自定义 controller 中）

```python
from module_file.service.filesystem import FileService
from module_file.dependencies.filesystem import get_file_service

@router.post("/attach")
async def attach(
    service: FileService = Depends(get_file_service),
    current_user_id: str = Depends(get_current_user_id),
):
    entry = await service._upload_content(content, "a.txt", pid=None, owner_user_id=current_user_id)
```

> 约定：跨模块仅导入 `module_file.client`（或 `dependencies/service`），**不要**直接操作 module_file 的 dao/do 内部结构。

### Celery 任务进程中

`FileClient` 的 DAO 方法用 `@DaoRel` 自管事务，在 worker 的 `run_async` 协程里可直接 `await file_client.xxx(...)`，无需额外处理。

## 5. 目录结构

```
module_file/
├── client.py                  跨模块门面(FileClient 单例 file_client)
├── config/
│   ├── filesystem.py          全局存储单例(按 conf.file_system.storage_type)
│   ├── filetype.py            文件类型配置
│   └── server.py              /file 子应用挂载
├── controller/filesystem.py   REST 接口
├── dao/                       file_entry_dao / file_content_dao
├── dependencies/filesystem.py DI 工厂
├── do/filesystem.py           表模型+请求/响应模型
├── service/filesystem.py      业务逻辑(FileService)
└── utils/multi_storage/       存储抽象
    ├── storage_factory.py     工厂(按配置类型实例化)
    ├── do/storage_config.py   StorageType(LOCAL/S3/RUSTFS) + 配置类注册
    └── session/
        ├── interface/strorage_interface.py   存储接口协议
        └── impl/storage_local.py             本地磁盘实现(HMAC签名代理)
        └── impl/storage_s3.py                S3协议实现(rustfs/minio/oss)
```
