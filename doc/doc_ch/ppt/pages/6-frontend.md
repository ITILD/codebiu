---
layout: two-cols
layoutClass: gap-8
glow: right
---

# 前端结构：Vue3 + Element Plus

## 目录速览

```
src/
├── api/            # 后端接口封装(按模块分目录)
├── assets/         # 静态资源与全局样式(自然笔记风主题)
├── components/     # 公共组件(SysHeader/SysSidebar...)
├── pages/          # 页面(文件路由,自动生成)
│   ├── index.vue       # 首页
│   └── _sys/           # 管理后台
│       ├── _sys.vue    # 布局容器
│       ├── file/       # 文件管理
│       └── rag/        # 知识库
├── stores/         # Pinia 状态(auth/sys/router)
├── types/          # TS 类型定义(与后端 DO 对应)
└── utils/http.ts   # axios 封装(自动解包)
```

::right::

## 新页面开发三件套

**1. 类型** `types/demo.ts`

```ts
type Demo = { id: string; name: string }
```

**2. 接口** `api/demo/index.ts`

```ts
export const listDemo = () =>
  http_base_server.get<Demo[]>('/demo/list')
```

**3. 页面** `pages/_sys/demo/index.vue`

- 文件路径即路由(无需手动注册)
- 组件**优先用 Element Plus**
  (`el-table` / `el-form` / `el-dialog`...)

<div class="note-tip">
布局约定: 顶栏+左侧模块菜单已全局化在 App.vue,新页面只需专注内容区。
</div>
