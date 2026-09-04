# base_web

This template should help get you started developing with Vue 3 in Vite.

## Recommended IDE Setup

[VSCode](https://code.visualstudio.com/) + [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (and disable Vetur).

## Type Support for `.vue` Imports in TS

TypeScript cannot handle type information for `.vue` imports by default, so we replace the `tsc` CLI with `vue-tsc` for type checking. In editors, we need [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) to make the TypeScript language service aware of `.vue` types.

## Customize configuration

See [Vite Configuration Reference](https://vite.dev/config/).

## Project Setup

```sh
pnpm install
```

### Compile and Hot-Reload for Development

```sh
pnpm dev
```

### Type-Check, Compile and Minify for Production

```sh
pnpm build
```

### Run Unit Tests with [Vitest](https://vitest.dev/)

```sh
pnpm test:unit
```

### Run End-to-End Tests with [Playwright](https://playwright.dev)

```sh
# Install browsers for the first run
npx playwright install

# When testing on CI, must build the project first
pnpm build

# Runs the end-to-end tests
pnpm test:e2e
# Runs the tests only on Chromium
pnpm test:e2e --project=chromium
# Runs the tests of a specific file
pnpm test:e2e tests/example.spec.ts
# Runs the tests in debug mode
pnpm test:e2e --debug
```

### Lint with [ESLint](https://eslint.org/)

```sh
pnpm lint
```

## 项目架构（Feature-based / 模块化）

业务代码按「业务模块」垂直切分，同一业务模块的页面、接口、类型、组件、状态聚合在同一个文件夹，
与后端 `module_*` 模块一一对应；删除某个模块文件夹即等于下线该功能，不会遗留僵尸代码。

```sh
src/
├── app/                     # 应用壳层（可依赖任何模块）
│   └── components/          # SysHeader / SysSidebar / SysFooter / 系统设置面板
├── modules/                 # 业务模块层（与后端 module_* 一一对应）
│   └── <module>/            # 如 authorization / ai / rag / main / geometry ...
│       ├── api/             # 该模块的接口封装（相对路径互相引用）
│       ├── types/           # 该模块的类型定义
│       ├── components/      # 模块私有组件（跨模块使用需显式 import）
│       ├── stores/          # 模块状态（可选）
│       ├── utils/           # 模块工具类（可选）
│       └── pages/           # 自动路由页面 → URL /<module>/<page>
├── pages/                   # 路由入口层：全局页面（首页 / 后台工作台 admin / 设置 / 404）
├── common/                  # 公共层：与业务无关的通用资源，按类型划分
│   ├── api/http.ts          # 全局 HTTP 客户端
│   ├── components/          # TableSearchBar / chat / ide / icons 通用组件
│   ├── composables/         # usePermission 等组合式函数
│   ├── enums/ i18n/ stores/ types/ utils/
│   └── ...
├── assets/  router/  App.vue  main.ts
```

分层依赖规则（自上而下单向依赖）：

```
pages → app → modules → common
```

- `modules` 内部文件使用相对路径（`../api/xxx`），保证模块自包含、可整体删除；
- 跨模块只能引用其 `api/types/components`，禁止引用其他模块的 `pages`；
- `common` 不允许反向依赖 `modules`（唯一例外：会话状态 `common/stores/auth.ts` 依赖
  `authorization` 模块的登录接口）。

自动路由由 `unplugin-vue-router` 完成：`vite.config.ts` 中 `routesFolder` 同时扫描
`src/pages` 与 `src/modules/*/pages`，模块页面按模块规范挂载到 `/<模块名>/<页面>` 路径下，
并通过 `extendRoute` 为除首页/404 外的路由写入 `meta.admin` 标记（登录拦截与侧边栏显示的依据），
侧边栏菜单（`app/components/layout/SysSidebar.vue`）与路由路径保持一致。
