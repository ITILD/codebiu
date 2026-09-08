# 全站风格与 UnoCSS 写法规范

> 适用范围: `frontend/vue3/src` 下全部页面与组件。
> 配置来源: `uno.config.ts`（shortcut / rule 定义）+ `src/assets/base.css`（Element Plus 主题变量）。

---

## 1. 设计主题: 淡绿色 · 自然笔记风

- **灵感**: 苔绿主色 + 米白纸张底色 + 笔记本格线，整体像一本自然笔记。
- **双模式**: 全部颜色必须同时提供亮色与 `dark:` 暗色（墨绿基调）取值。
- **实现层次**:
  - `uno.config.ts` → `note-*` shortcuts（模板中直接使用）；
  - `base.css` → `--note-*` / `--el-*` CSS 变量（style 块或 Element Plus 主题化用）。

### 1.1 颜色令牌总表

| 令牌 | 亮色 | 暗色 | 用途 |
| --- | --- | --- | --- |
| `bg-note-paper` | `#fafaf5` | `#0d1711` | 页面根底色（纸张） |
| `bg-note-soft` | `#f4f8f2` | `#15231c` | 侧边栏 / 卡片内衬 / 表头 |
| `bg-note-card` | `#ffffff` | `#18271e` | 卡片白（纸片） |
| `bg-note-tint` | `#eef6ef` | `#1d3a2e` | 淡绿强调底（图标容器/悬浮态） |
| `bg-note-green` | `#6b9e78` | `#4f8d67` | 苔绿实底（主按钮/徽点） |
| `text-note` | `#3f5348` | `#ddebe2` | 主文字（标题/正文重点） |
| `text-note-sub` | `#5a6b5f` | `#a6c0b1` | 次级文字（说明/辅助信息） |
| `text-note-green` | `#557f61` | `#88d2a7` | 苔绿强调文字（链接/高亮） |
| `border-note` | `#e3ebe2` | `#263a2f` | 常规边框 |
| `border-note-green` | `#a9c9b1` | `#3f6b52` | 强调边框（悬浮/选中） |
| `shadow-note` | `0 2px 12px rgba(108,191,143,.14)` | 同左 | 柔和纸片影 |
| `bg-note-gradient` | 三段淡绿渐变 | 墨绿渐变 | Hero / 页头大区块 |
| `bg-note-glass` | `rgba(244,248,242,.85)` | `rgba(21,35,28,.85)` | 吸顶毛玻璃（须配 `backdrop-blur-md`） |

`base.css` 中同名 CSS 变量: `--note-green` `--note-green-deep` `--note-paper` `--note-soft` `--note-border` `--note-text`（亮暗自动切换）。

### 1.2 语义色（状态）允许保留

状态含义的颜色不映射 `note-*`，直接用 Element Plus / Tailwind 语义色，全站约定:

| 场景 | 用色 |
| --- | --- |
| 成功 / 收入 / 通过 | `text-green-600`、`type="success"` |
| 失败 / 支出 / 危险操作 | `text-red-500`、`type="danger"` |
| 警告 | `text-amber-500`、`type="warning"` |
| 中性 / 占位 | `text-note-sub`、`type="info"` |

**例外白名单**: 有意使用非令牌色的位置必须加注释说明原因（如 voice.vue 录音标签内的 `bg-white` 脉冲点、CalendarYear 今日格上的白点），避免后续被"规范清扫"误改。

---

## 2. 页面结构模板

### 2.1 标准页面容器

```html
<template>
  <div p-4 md:p-6 w-full>
    <!-- 页面标题: 标题 + 一句话说明, 左对齐 -->
    <div mb-4>
      <h2 text-lg font-bold text-note>页面标题</h2>
      <p text-xs text-note-sub mt-1>🌿 一句话说明本页功能</p>
    </div>
    ...
  </div>
</template>
```

- 优先用 shortcut `page-shell`（等价 `p-4 md:p-6 w-full`）；
- 全高布局页（文件管理器等）可用 `h-app` / `max-h-app`（视口减吸顶导航高度）；
- 窄幅工具页可加 `max-w-6xl mx-auto` 居中，但内外边距仍须遵循 `p-4 md:p-6`。

### 2.2 卡片

```html
<!-- 通用卡片: 首选 page-card shortcut(已含边框宽度/圆角/底色/阴影) -->
<div page-card>...</div>

<!-- 便签风卡片(可悬浮交互, 圆角更大) -->
<div rounded-2xl border border-note bg-note-card shadow-note
  hover:border-note-green hover:-translate-y-0.5 transition-all>
  ...
</div>

<!-- 可点击选中卡片 -->
<div cursor-pointer rounded-lg p-3 bg-note-card border border-note shadow-note
  transition-colors hover:bg-note-tint
  :class="{ 'ring-2 ring-note': active }">
  ...
</div>
```

- 卡片标题行用 `card-toolbar`（`mb-3 flex flex-wrap items-center justify-between gap-2`）；
- 卡片内标题文字加 `text-note`，说明文字加 `text-note-sub`。

### 2.3 表格页

表格样式已由 `base.css` 全局主题化（`.el-table.el-table`: 苔绿表头 + 圆角 10px + 纸片影），无需逐页处理:

```html
<TableSearchBar v-model="queryParams" :fields="searchFields"
  @search="handleSearch" @reset="handleSearch">
  <template #actions>
    <el-button type="primary" @click="handleCreate">新增</el-button>
  </template>
</TableSearchBar>

<el-table :data="tableData" v-loading="loading" stripe w-full>...</el-table>

<!-- 分页: 手机居中, 桌面靠右 -->
<div mt-4 flex flex-wrap justify-center sm:justify-end>
  <el-pagination ... />
</div>
```

需要强调容器感时把表格包进便签风卡片:

```html
<div rounded-2xl border border-note bg-note-card shadow-note overflow-hidden>
  <el-table ...>...</el-table>
</div>
```

搜索一律复用 `TableSearchBar`，不要手写 `el-input + el-button` 组合。

### 2.4 统计卡片行

```html
<div grid grid-cols-2 md:grid-cols-4 gap-3>
  <div v-for="card in statCards" :key="card.key" ...同 2.2 选中卡片...>
    <div text-xs text-note-sub>{{ card.label }}</div>
    <div text-2xl font-bold mt-1 :class="card.color">{{ card.value }}</div>
  </div>
</div>
```

数值色只用语义色（见 1.2），标签统一 `text-note-sub`。

### 2.5 空状态

```html
<div py-16 flex flex-col items-center text-note-sub>
  <el-icon text-5xl mb-3 class="opacity-40"><FolderOpened /></el-icon>
  <p m-0>暂无数据, 点击右上角"新建"开始</p>
</div>
```

---

## 3. UnoCSS 写法规范

### 3.1 优先级顺序

1. **项目 shortcut**（`page-card` `page-shell` `card-toolbar` `bg-note-*` `text-note*` …）；
2. **presetWind3 原子类** + `dark:` 变体；
3. **CSS 变量**（style 块中用 `var(--note-*)`）；
4. 最后才允许任意值 `bg-[#xxxxxx]`，且必须补 `dark:` 变体或注释原因。

### 3.2 Attributify 使用约定

- 简单视觉属性直接写成无值属性: `<div flex items-center gap-2 mt-1>`；
- **含方括号任意值 / 伪类复杂的类必须写进 `class` 属性**（attributify 解析陷阱）:

```html
<!-- ✅ 正确 -->
<SysHeader class="bg-note-glass backdrop-blur-md" />
<div class="h-[60vh] md:h-[80vh]">

<!-- ❌ 错误: attributify 模式下可能不生成 -->
<div bg-note-glass backdrop-blur-md>
<div h-[60vh]>
```

### 3.3 变体分组与深色模式

```html
<!-- ✅ 分组写法 -->
<div hover:(border-note-green -translate-y-0.5) md:(p-6 text-lg)>

<!-- ✅ 颜色必须成对出现亮/暗 -->
<div bg-note-card border border-note text-note>
```

裸颜色类（`bg-white` `bg-gray-*` `text-gray-*`）**禁止出现**，一律换成对应 `note-*` 令牌或语义色。

### 3.4 style 块内

- 需要主题联动时用 CSS 变量: `background: var(--note-soft);`（暗色自动切换）；
- 覆盖 Element Plus 时注意特异性，参考 `base.css` 中 `.el-table.el-table` 双写手法；
- 尽量不写死 hex；确需写死时取 1.1 表中的值并加 `html.dark` 对应分支。

### 3.5 常用 shortcut 速查

| shortcut | 展开值 |
| --- | --- |
| `page-shell` | `p-4 md:p-6 w-full` |
| `page-card` | `p-4 rounded-lg bg-note-card border border-note shadow-note` |
| `card-toolbar` | `mb-3 flex flex-wrap items-center justify-between gap-2` |
| `flex-center` / `center` | `flex items-center justify-center` / `flex justify-center items-center` |
| `mini-text-center-between` | `flex items-center justify-between` |
| `h-app` / `max-h-app` | `h-[calc(100vh-3.5rem)] md:h-[calc(100vh-4rem)]` |
| `text-ellipsis` / `scrollbar-hide` | 溢出省略 / 隐藏滚动条 |
| `bg-gradient-primary` | 主色 135° 渐变 |
| `note-lined-paper` / `note-margin-line` | 横线纸 / 装订线（base.css） |

新增通用样式时先看本表能否组合；确需新增 shortcut 统一加在 `uno.config.ts` 的"淡绿色自然笔记风"分组内并写中文注释。

---

## 4. 图标与组件细则

- 图标统一用 UnoCSS 图标类: `i-ep-*`（Element Plus 集）、`i-vscode-icons-*`，通过 `presetIcons` 引入；
- 图标容器底: `w-10 h-10 rounded-xl bg-note-tint flex-center`，图标色 `text-note-green`；
- 标签 `el-tag` 已全局圆角胶囊化（`base.css`），类型只用 `success/warning/danger/info`；
- 对话框/抽屉圆角已全局处理，不要再逐个覆盖。

---

## 5. 自检清单（提交前过一遍）

- [ ] 所有颜色都有暗色取值（或使用自带 dark: 的 note-* shortcut）？
- [ ] 没有 `bg-white` / `bg-gray-*` / `text-gray-*` 等裸灰白类？
- [ ] 含 `[ ]` 任意值的类写进了 `class` 属性？
- [ ] 卡片用 `page-card` / 便签风组合，而不是裸 `el-card` 或手写白底圆角？
- [ ] 页面容器是 `page-shell`（或 `p-4 md:p-6 w-full`），标题带 `text-note` + `text-note-sub` 说明？
- [ ] 搜索栏复用 `TableSearchBar`，分页位置 `justify-center sm:justify-end`？
- [ ] 语义色只用于状态；非令牌色有注释说明？

> 范本文件: `src/modules/rag/pages/project.vue`（卡片+表格）、`src/modules/main/pages/dict.vue`（页面标题）、`src/modules/api_test/pages/index.vue`（统计卡片）、`src/pages/index.vue`（Hero）。
