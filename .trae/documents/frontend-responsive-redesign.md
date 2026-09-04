# 前端主页/工作台/后台页重构 + 全站响应式 实施计划

## Context（背景）

当前前端已具备淡绿自然笔记风主题（uno.config.ts 的 `note-*` shortcuts）和基础响应式（仅 768 单断点），但存在以下问题：

1. **布局壳**：头部为文档流非吸顶、无面包屑；侧边栏只有 768 一档断点，平板(768-1024)与手机体验未区分
2. **主页**：结构简单，无登录态感知、无实时系统状态、模块入口与侧边栏菜单数据不同源
3. **后台页(admin.vue)**：统计卡是假数据 `'-'`，且用 `gray-*` 配色与全局 `note-*` 淡绿主题不统一
4. **模块页**：部分表格固定列宽导致小屏横向滚动、搜索工具栏未做换行收缩、个别统计卡 `min-w-[130px]` 硬编码

**用户已确认**：主功能页=布局壳+全部模块页统一响应式化；导航增强仅加面包屑（不做 tags-view）；后台页接真实数据（getStatusCache）。

## 全局约束（每步必须遵守）

- **UnoCSS attributify 陷阱**：类名含 `/`、`[`、`]` 的任意值类（如 `md:min-w-[130px]`、`bg-[rgba(...)]`）**必须写在 `class="..."` 属性内**，禁止裸 attributify 属性，否则 InvalidCharacterError 整页空白（项目历史教训）
- **h-app 公式不可破坏**：`h-app/max-h-app = calc(100vh-3.5rem) md:calc(100vh-4rem)` 被 7 个页面（file/index、ai/chat、ai/voice、rag/conversation、monitor/uistore、life/baby_name、template/infoview）及 SysSidebar 依赖 → **header 高度必须保持 `h-14 md:h-16` 不变**，面包屑只能在 header 内部同排
- 不加 Suspense / 不加路由 Transition（历史坑，切页空白）
- 新代码中文注释；保持 `note-*` 淡绿笔记风

## Step 1 基础设施（无 UI 变化，低风险先行）

### 1.1 sys.ts 断点升级 — `src/common/stores/sys.ts`

用 `@vueuse/core` 的 `useBreakpoints({ md: 768, lg: 1024 })` 替换手写 resize 监听：

- `isMd: breakpoints.greater('md')`（语义微调 >768 → >=768，与 CSS `md:` 对齐；768px 设备从抽屉变为折叠侧栏）
- 新增 `isLg: breakpoints.greater('lg')`
- 删除 `window.onresize = ...` 全局赋值
- 现有调用方（SysHeader 汉堡条件、SysSidebar v-if/watch）零改动

### 1.2 菜单数据抽离

- **新建 `src/common/config/menu.ts`**：`MenuItem` 接口 + `menuItems` 数组从 SysSidebar 原样迁出，新增 `desc?: string` 字段（主页模块卡文案用），导出纯函数 `findMenuTrail(path): MenuItem[]`（路径匹配菜单树，面包屑用）
- **新建 `src/common/composables/useMenu.ts`**：`useVisibleMenu()` 将权限过滤逻辑（原 visibleMenuItems computed）迁入，SysSidebar/面包屑/主页共用
- **新建 `src/common/composables/useRecentPages.ts`**：最近访问记录（vueuse `useLocalStorage('note:recent-pages', [])`，条目 `{path,title,ts}`，去重+unshift+上限 8 条）
- 采集点：App.vue 加 `watch(() => route.path, ...)`，仅 `route.meta.admin` 页面调用 `pushRecent`，标题取 `findMenuTrail(p).at(-1)?.title`

### 1.3 SysSidebar 切换共享菜单（行为不变）

`src/app/components/layout/SysSidebar.vue` 删除本地 menuItems/visibleMenuItems，改 import 共享层。

**验证**：type-check + build；桌面/手机宽度菜单与现状一致、权限过滤生效

## Step 2 布局壳现代化

### 2.1 uno.config.ts 新增 shortcut

```ts
// 毛玻璃纸底(header 吸顶用; shortcut 不支持 /80 透明度修饰,故单独定义)
'bg-note-glass': 'bg-[rgba(244,248,242,0.85)] dark:bg-[rgba(21,35,28,0.85)]',
```

### 2.2 SysHeader — `src/app/components/layout/SysHeader.vue`

- 左区：汉堡(仅 admin 且 !isMd) + Logo + **SysBreadcrumb**(`hidden md:block ml-4 flex-1 min-w-0`，过长 truncate)
- 外层 `flex justify-between` → `flex items-center`，右区 shrink-0
- 汉堡条件保持 `isAdmin && !isMd`（<768 才显示；768-1024 有折叠侧栏）

### 2.3 App.vue — sticky 毛玻璃头部

```html
<SysHeader
  class="sticky top-0 z-20 h-14 md:h-16 border-b border-note shrink-0
         bg-note-glass backdrop-blur-md"
/>
```

内容区容器与 `items-start` 保持不变（sidebar sticky 前提）。

### 2.4 SysBreadcrumb — 新建 `src/app/components/layout/SysBreadcrumb.vue`

- `el-breadcrumb` + `findMenuTrail(route.path)` 生成 `['首页','分组','当前页']`
- 仅 admin 路由且路径有匹配时显示；`hidden md:block`

### 2.5 SysSidebar 三档响应式

- 手机(<768)：el-drawer 保留
- 平板(768-1024)：默认折叠 64px 图标栏
- 桌面(>=1024)：默认展开 230px

```ts
const isCollapse = ref(!sysSettingStore.sysStyle.isLg)  // 平板折叠/桌面展开
watch(() => sysSettingStore.sysStyle.isLg, (v) => { isCollapse.value = !v })  // 跨断点重置
```

`el-aside` sticky top-16 / max-h-app 不变。

**验证**：375/768/1024/1440 四档断点走查；滚动吸顶；打开 ai/chat 确认 h-app 无双滚动条

## Step 3 主页重设计 — `src/pages/index.vue`

```
max-w-5xl mx-auto p-4 md:p-8
├─ Hero(bg-note-gradient + note-lined-paper + 🌿)
│   ├─ 已登录: 时段问候(早上好/下午好/晚上好,{nickname||username})
│   │          + 实时状态徽章行(getStatusCache → CPU/内存/磁盘 百分比胶囊,失败静默隐藏)
│   │          + 最近访问快捷卡(useRecentPages 前 6 条,空则隐藏)
│   │          + CTA「进入工作台」
│   └─ 未登录: 现有引导文案 + 登录/工作台 CTA(保持)
├─ 功能模块卡: 数据源 useVisibleMenu() 有 children 的分组(desc 用 menu.ts 新字段)
│   grid-cols-1 sm:grid-cols-2 lg:grid-cols-3(保留)
└─ 底部小语(不变)
```

注意：状态徽章仅在已登录分支调用接口，try/catch 静默降级（避免 401 全局报错）。

## Step 4 后台页重构 — `src/pages/admin.vue`

- **主题统一**：全部 `gray-*` → `note-*`（bg-note-card/border-note/shadow-note/text-note 系）
- 欢迎区：时段问候 + 副文案 + 刷新按钮
- 统计卡 `grid grid-cols-2 lg:grid-cols-4 gap-4`，接真实数据 `getStatusCache()`：

| 卡片 | 字段 | 副文案 |
|---|---|---|
| CPU | `hardware.cpu.percent` | `{cores}核/{threads}线程` |
| 内存 | `hardware.memory.percent` | `{used}/{total} GB` |
| 磁盘 | `hardware.disk.percent` | `{used}/{total} GB` |
| 网络 | network 连通率 | `成功 {ok}/{total}`（null → '-'） |

- 数据加载：onMounted + 60s 自动刷新（对齐后端 60s 缓存）+ onUnmounted 清定时器；失败 try/catch 静默
- 快捷入口：useVisibleMenu 抽分组首页（perm 过滤，bg-note-tint）
- 最近访问：useRecentPages 前 8 条

## Step 5 模块页响应式统一（分 2 批）

### 统一模式（逐页套用）

1. **表格**：数据列固定 `width` → `min-width`；操作列保留 `fixed="right"` 但收窄，移动端可 `:fixed="sysStyle.isMd ? 'right' : false"`；el-table 自带横向滚动
2. **工具栏**：`flex flex-wrap items-center gap-2`；搜索框 `w-full sm:w-56`；主操作按钮 `ml-auto`
3. **统计卡**：`grid grid-cols-2 md:grid-cols-4 gap-3`，删除 `flex-1` + 裸 `min-w-[...]`
4. **Dialog**：保持 `width="90%"`，任意值 max-w 写 class 内；表单 `grid-cols-1 sm:grid-cols-2`
5. **根容器**：`bg-gray-50` → `bg-note-paper`；内容流页面 `p-4 md:p-6`，全屏工作台保持 `h-app`

### 批 A（高频页面）

| 文件 | 要点 |
|---|---|
| modules/file/pages/index.vue | 操作列 width=270 fixed → min-width 收窄；大小/时间列 width → min-width；搜索框 w-full sm:w-56 |
| modules/task/pages/queue.vue | 统计卡 flex+min-w-[130px] → grid 2/4 列；表格固定 width 列改 min-width |
| modules/authorization/user.vue | 操作列微调；role/dept/permission/casbin 同模式（casbin 双表格容器 grid-cols-1 xl:grid-cols-2） |

### 批 B（其余页面）

| 文件 | 要点 |
|---|---|
| rag/document.vue、member.vue | 套统一模式（project.vue 是正面范例不动） |
| rag/conversation.vue | h-app 布局：移动端会话列表/聊天区 `flex-col md:flex-row` 堆叠，列表 h-40 md:h-auto |
| ai/voice、model_config、ocr | bg-gray-50 → note-*；表格工具栏套模式 |
| ai/chat.vue | 仅微调（已有 h-app 满宽 flex） |
| monitor/server_status.vue | 状态卡 grid 2/4 列 + note-* 化 |
| monitor/uistore.vue | h-app 保留，确认移动端堆叠 |
| geometry/earth.vue | 3D 场景保留，工具浮层 max-h 溢出滚动 |
| life/baby_name、main/overview、dict、little_utils/todolist | 套统一模式 |
| template/* | overview/template/container 套模式；演示页(babylon/mediapipe/infoview)只查 attributify 陷阱 |

## Step 6 全量回归

- `pnpm type-check` + `pnpm build` 全绿
- 浏览器 375/768/1024/1440 四断点全站走查
- DevTools Console 无 InvalidCharacterError（attributify 专项）
- 未登录/已登录两态主页；断网时状态徽章隐藏不报错

## 风险点

1. h-app 公式依赖 header 高度不变 → 面包屑只在 header 内部
2. attributify 裸任意值类 → 全部写 class 属性
3. isMd 语义 >768→>=768 → 768px 恰好宽度需验证
4. 主页公开页调鉴权接口 → 徽章必须已登录分支内 + 静默容错
5. drawer 挂 body 与 sticky header 无冲突，但需确认毛玻璃不产生重影（必要时降级纯色）

## 关键文件

- `src/common/stores/sys.ts`（断点）
- `src/common/config/menu.ts`（新建，菜单共享）
- `src/common/composables/useMenu.ts`、`useRecentPages.ts`（新建）
- `src/app/components/layout/SysHeader.vue`、`SysSidebar.vue`、`SysBreadcrumb.vue`（新建）
- `src/App.vue`、`uno.config.ts`
- `src/pages/index.vue`、`src/pages/admin.vue`
- 模块页约 18 个（见 Step 5 清单）
