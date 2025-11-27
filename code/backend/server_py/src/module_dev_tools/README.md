# 开发辅助模块 (Module Dev Tools)

基于Python标准库 `string.Template` 的模板管理模块，提供模板字符串的增删改查和渲染功能。

## 功能特性

- ✅ 模板字符串的增删改查操作
- ✅ 基于 `string.Template` 的安全模板渲染
- ✅ 模板语法验证
- ✅ 分类管理和标签支持
- ✅ 分页查询和无限滚动
- ✅ 模板变量提取和验证

## API 接口

### 基础CRUD操作

- `POST /dev-tools/template_strings` - 创建模板字符串
- `GET /dev-tools/template_strings/list` - 分页查询模板列表
- `GET /dev-tools/template_strings/scroll` - 无限滚动查询
- `GET /dev-tools/template_strings/{id}` - 获取单个模板详情
- `PUT /dev-tools/template_strings/{id}` - 更新模板
- `DELETE /dev-tools/template_strings/{id}` - 删除模板

### 高级功能

- `POST /dev-tools/template_strings/render` - 渲染模板
- `GET /dev-tools/template_strings/category/{category}` - 按分类查询
- `GET /dev-tools/template_strings/search/{name}` - 按名称搜索
- `GET /dev-tools/template_strings/active/list` - 获取激活模板
- `POST /dev-tools/template_strings/validate` - 验证模板语法

## 模板语法

使用标准的 Python `string.Template` 语法：

```python
# 模板内容
"Hello ${name}! Welcome to ${company}."

# 渲染数据
{"name": "张三", "company": "CodeBiu"}

# 渲染结果
"Hello 张三! Welcome to CodeBiu."
```

## 数据模型

### TemplateString 字段

- `id`: 唯一标识符
- `name`: 模板名称
- `description`: 模板描述
- `template_content`: 模板内容
- `category`: 分类
- `tags`: 标签列表
- `is_active`: 是否激活
- `created_at`: 创建时间
- `updated_at`: 更新时间

## 使用示例

### 创建模板

```python
POST /dev-tools/template_strings
{
    "name": "欢迎邮件模板",
    "description": "新用户欢迎邮件模板",
    "template_content": "欢迎 ${username} 加入 ${company}！您的账号是：${account}",
    "category": "邮件模板",
    "tags": ["欢迎", "邮件"],
    "is_active": true
}
```

### 渲染模板

```python
POST /dev-tools/template_strings/render
{
    "template_id": "template_id_here",
    "variables": {
        "username": "张三",
        "company": "CodeBiu",
        "account": "zhangsan@example.com"
    }
}
```

## 依赖

- Python 3.11+
- FastAPI
- SQLModel
- string.Template (Python标准库)

## 开发说明

模块采用标准的MVC架构：

- `do/`: 数据模型层
- `dao/`: 数据访问层
- `service/`: 业务逻辑层
- `controller/`: API控制器层
- `dependencies/`: 依赖注入配置
- `config/`: 模块配置

模块已自动挂载到主应用的 `/dev-tools` 路径下。