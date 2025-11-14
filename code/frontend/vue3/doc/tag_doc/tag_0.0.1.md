# Vite + Vue 3 项目初始化规范

## 1. 项目概述

基于 Vite 和 Vue 3 的前端项目模板提供一个快速启动和开发的环境,专注于业务逻辑的开发。

### 1.1项目配置

| 类别           | 配置项     | 规范要求    |
| -------------- | ---------- | ----------- |
| **包管理器**   | 包管理工具 | pnpm        |
| **开发服务器** | 服务器工具 | Vite        |
| **前端框架**   | 主框架     | Vue 3       |
| **项目类型**   | 应用类型   | 前端SPA应用 |

### 1.2工程初始化

本地或 Git 托管网站上创建项目：

```bash
# 拉取基础代码（如果需要）
git clone http://zwork1.w1.luyouxia.net/gitea/codebiu_2025/base_web.git
```

## 2. 初始化 Vite + Vue 3 项目

### 2.1 创建新项目

```bash
# 使用官方脚手架创建项目
pnpm create vue@latest
```

### 2.2 配置选项说明

在交互式命令行中，建议选择以下配置（按空格键选择/取消选择）：

```
✔ 项目名称: base_web
✔ 选择功能: 
  ◉ TypeScript
  ◉ JSX 支持 (可选)
  ◉ Vue Router (单页应用)
  ◉ Pinia (状态管理)
  ◉ Vitest (单元测试)
  ◉ Playwright (端到端测试)
  ◉ ESLint (代码检查)
  ◉ Prettier (代码格式化)
✔ 试验特性: 
  ◉ Oxlint (试验阶段)
  ◉ rolldown-vite (试验阶段)
✔ 是否跳过示例代码: No (推荐保留示例代码学习)
```


## 3. 迁移代码（可选）

如果需要将生成的项目迁移到其他目录：

```bash
# 重命名README文件
mv ./base_web/README.md ./base_web/base_web.md
# 拷贝基础代码
cp -r ./base_web/* ./
# 删除原文件夹（Windows系统）
rm -r -fo ./base_web
# 删除原文件夹（linux系统）
# rm -rf ./base_web 
```

## 4. 安装依赖并运行

```bash
# 安装依赖
pnpm install

# 启动开发服务器
pnpm dev

# 构建生产版本
pnpm build
```

## 5. 添加 Git 配置

创建 `.gitignore` 文件并添加必要的忽略规则。
本地.git\config文件内添加账号密码
```diff
[remote "origin"]
-	# url = http://zwork1.w1.luyouxia.net/gitea/codebiu_2025/base_web.git
+	url = http://name:passworld@zwork1.w1.luyouxia.net/gitea/codebiu_2025/base_web.git
+ [user]
+        name = XXX
+        email = XXX

```


## 项目结构说明

项目初始化完成后，你将获得一个包含以下功能的 Vue 3 项目：
- TypeScript 支持
- Vue Router 单页应用路由
- Pinia 状态管理
- Vitest 单元测试
- Playwright 端到端测试
- ESLint 代码检查
- Prettier 代码格式化

现在你可以开始开发你的 Vue 3 应用了！