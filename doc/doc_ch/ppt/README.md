# codebiu 开发入门 PPT

基于 [Slidev](https://sli.dev) 制作的**新成员上手演示文稿**，内容覆盖：项目概览、系统架构、环境搭建、后端 MVC 分层、新模块开发六步法、前端结构、Casbin 权限体系与 Git 协作规范。

## 使用

```bash
# 安装依赖
pnpm i

# 开发预览(默认 50004 端口)
pnpm run dev

# 构建 SPA 静态站点(部署到服务器子路径用 build_base)
pnpm run build
pnpm run build_base

# 导出 PDF / PPTX / PNG
pnpm run export-pdf
pnpm run export-pptx
```

## 结构

```
ppt/
├── slides.md          # 入口:按顺序引入 pages/*.md
├── pages/             # 每页一个 md 文件
│   ├── 0.md           # 首页
│   ├── toc.md         # 目录
│   ├── 1-project.md   # 项目概览
│   ├── 2-arch.md      # 系统架构
│   ├── 3-env.md       # 环境搭建
│   ├── 4-backend.md   # 后端 MVC 分层
│   ├── 5-module.md    # 新模块开发六步法
│   ├── 6-frontend.md  # 前端结构
│   ├── 7-auth.md      # 权限体系
│   ├── 8-git.md       # Git 协作规范
│   └── end.md         # 尾页
├── style.css          # 全局学术风格样式(明暗自适应)
├── global-bottom.vue  # 全局背景光效(苔绿自然色)
└── uno.config.ts      # UnoCSS 配置
```

## 修改提示

- 光效控制：每页 frontmatter 的 `glow` / `glowOpacity` / `glowSeed`
- 增删页面：改 `slides.md` 的引入列表，页面写在 `pages/` 下
- 交互强调：`<span v-mark.green>重点</span>` 手绘标记

## 关联文档

- 开发文档：`doc/doc_ch/`
- 部署运维：`deveops/`
