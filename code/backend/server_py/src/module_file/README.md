# module_file 网络文件系统模块

完整的网络文件系统（虚拟文件树 + 可切换物理存储），支持 `local` / `s3`(MinIO/rustfs等) 两种存储的**无缝切换**，对所有调用方（前端 / 其他后端模块）暴露**完全一致**的接口。

## 1. 架构

```
前端(Vue3) / 其他模块(FileService)
        │  统一 REST 接口 (/file/filesystem/*)
        ▼
controller/filesystem.py ──► service/filesystem.py (FileService)
        │                          │
        │                          ├── dao/file_entry_dao.py    虚拟文件树(条目: 文件+目录, pid树, 逻辑路径)
        │                          ├── dao/file_content_dao.py  物理内容(内容哈希去重, 引用计数)
        │                          ▼
        │                  StorageInterface(存储抽象)
        │                          ├── storage_local.py  本地磁盘(aiofiles)
        │                          └── storage_s3.py     S3协议(MinIO/rustfs/oss, aioboto3)
        ▼
config/filesystem.py: 按 conf.file_system.storage_type 启动时构建全局存储单例
```

核心设计：

- **虚拟文件树与物理存储解耦**：`file_entry` 表记录文件/目录树（pid + logical_path），`file_content` 表记录物理内容（content_hash 主键、physical_storage 物理键、storage_type 来源、ref_count 引用计数）。
- **内容哈希去重**：同一内容全系统仅存一份物理文件，复制/秒传零成本；引用计数归零自动清理物理文件。
- **存储无关**：业务层只见 `StorageInterface`（save/load/iter_chunks/delete/exists/size/list + 分片上传五件套），切换存储不改一行业务代码。

## 2. 存储根目录语义

- `storage_type: local`：本地目录 `base_dir` 作为文件系统根目录（未配置时默认 `dir.base_child.upload`），物理键 `uploads/{date}/{hash}{ext}` 解析为 `base_dir/uploads/...`。
- `storage_type: s3`：bucket（如 `bucket0`）作为根目录，物理键即 bucket 内的 object key。

`config.dev.yaml`:

```yaml
file_system:
  storage_type: s3            # local | s3 二选一
  max_size: 10                # 直传单文件上限(MB),超过自动走分片上传
  allowed_extensions:         # MIME 白名单(支持 image/* 通配),空=不限制
    - "application/pdf"
    - "image/*"
  # s3 / minio / rustfs 共用以下 S3 协议配置
  endpoint_url: "http://127.0.0.1:20004"
  access_key: "minioadmin"
  secret_key: "minioadmin"
  bucket: "bucket0"
  region: "us-east-1"
  secure: false
```

- `local` 无需 S3 配置，默认落盘 `dir.base_child.upload` 目录（可用 `base_dir` 覆盖）。
- 切换存储前先调用 `POST /file/filesystem/migrate` 迁移历史物理内容（支持断点续迁），再修改配置重启即可，前端完全无感。

## 3. REST 接口（前后端协议，与存储类型无关）

挂载前缀 `/file/filesystem`，权限码 `main:file:read/create/update/delete/migrate`。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/upload` | 小文件直传（multipart 表单，哈希去重秒传） |
| POST | `/multipart/init` | 初始化分片上传（返回会话凭证；内容已存在时 `is_existing=true` 秒传） |
| PUT | `/multipart/{upload_id}/parts/{part_number}` | 上传单个分片（body 为二进制，最后一片可小于标准分片） |
| GET | `/multipart/{upload_id}/parts` | 查询已上传分片（断点续传） |
| POST | `/multipart/{upload_id}/complete` | 完成上传（合并分片、SHA-256 校验、按真实哈希归位、建条目） |
| DELETE | `/multipart/{upload_id}` | 取消分片上传并清理已传分片 |
| POST | `/upload-complete` | 秒传建条目（init 返回 `is_existing=true` 后调用） |
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

### 分片上传协议（大文件 >10MB 前端自动分流）

1. **计算哈希**：前端用 `crypto.subtle` 计算 SHA-256。
2. **初始化**：`POST /multipart/init`（filename/file_size_bytes/content_hash）→ 返回 `upload_id`（HMAC 签名会话凭证，自包含物理键与存储会话ID，24h 有效）与 `part_size`（8MB）。若内容已存在返回 `is_existing=true`，跳到第 4 步即秒传。
3. **上传分片**：按 `part_size` 切片，逐片 `PUT /multipart/{upload_id}/parts/{n}`（body 为二进制），保存响应中的 `etag`。
4. **完成**：`POST /multipart/{upload_id}/complete`（filename/pid/parts 列表）→ 服务端合并分片、流式计算真实 SHA-256、按哈希归位物理文件（同内容自动去重）、创建虚拟条目。秒传场景改调 `POST /upload-complete`。
5. **中断恢复**：`GET /multipart/{upload_id}/parts` 查询已传分片后续传；`DELETE /multipart/{upload_id}` 取消并清理。

> 分片上传在 local 与 s3 下协议完全一致：s3 使用原生 Multipart Upload；local 分片暂存 `base_dir/.multipart/` 下，完成时合并。

## 4. 其他模块如何操作文件

跨模块仅依赖 `FileService`（或 DI 工厂），不要直接操作 module_file 的 dao/do 内部结构。

```python
from module_file.service.filesystem import FileService

service = FileService()

# —— 增 ——
entry = await service.upload_file(upload_file, description, pid)       # HTTP multipart 直传
entry = await service._upload_content(data_bytes, "report.pdf", pid=pid)  # 字节内容直传(≤max_size)
entry = await service.create_entry(EntryCreateRequest(...))            # 秒传建条目
folder = await service.mkdir_p("/rag/exports")                         # mkdir -p

# —— 删 ——
await service.delete_file(entry.id)      # 文件
await service.delete_folder(folder.id)   # 目录(递归)

# —— 改 ——
await service.rename(entry.id, "v2.pdf")
await service.move(entry.id, target_pid)
await service.copy_entry(entry.id, target_pid)  # 内容哈希去重,零物理复制

# —— 查 ——
entry = await service.get_file_entry(entry_id)
entry = await service.get_by_path("/rag/docs/report.pdf")
page = await service.list_by_pid(pid, PaginationParams(page=1, size=100))
page = await service.search("report", PaginationParams(page=1, size=50))
data: bytes = await service.read_file_bytes(entry.id)
text: str = await service.read_file_text(entry.id)
async for chunk in service.stream_entry_chunks(entry.id):  # 大文件流式
    ...
stats = await service.get_stats()  # 占用统计

# —— 底层直连(不建虚拟条目,仅临时文件场景) ——
await service.storage.save("tmp/x.bin", b"...")
data = await service.storage.load("tmp/x.bin")
```

### FastAPI 依赖注入（在自定义 controller 中）

```python
from module_file.dependencies.filesystem import get_file_service

@router.post("/attach")
async def attach(
    service: FileService = Depends(get_file_service),
    current_user_id: str = Depends(get_current_user_id),
):
    entry = await service._upload_content(content, "a.txt", pid=None, owner_user_id=current_user_id)
```

### Celery 任务进程中

`FileService` 的 DAO 方法用 `@DaoRel` 自管事务，在 worker 的 `run_async` 协程里可直接 `await service.xxx(...)`，无需额外处理。

## 5. 目录结构

```
module_file/
├── config/
│   ├── filesystem.py          全局存储单例(按 conf.file_system.storage_type)
│   ├── filetype.py            文件类型配置
│   └── server.py              /file 子应用挂载
├── controller/filesystem.py   REST 接口
├── dao/                       file_entry_dao / file_content_dao
├── dependencies/filesystem.py DI 工厂
├── do/filesystem.py           表模型+请求/响应模型
├── service/filesystem.py      业务逻辑(FileService,含分片上传)
└── utils/multi_storage/       存储抽象
    ├── storage_factory.py     工厂(按配置类型实例化)
    ├── do/storage_config.py   StorageType(LOCAL/S3/RUSTFS) + 配置类注册
    └── session/
        ├── interface/strorage_interface.py   存储接口协议(含分片五件套)
        └── impl/storage_local.py             本地磁盘实现(分片暂存+合并)
        └── impl/storage_s3.py                S3协议实现(原生 Multipart Upload)
```
