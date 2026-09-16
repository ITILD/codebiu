import {
  defineConfig,
  presetAttributify,     // 属性化模式预设：支持用 HTML 属性风格写样式，如 text="red lg"
  presetIcons,           // 图标预设：支持使用类名引入图标，如 i-mdi-home
  presetTypography,      // 排版预设：提供文章友好的默认文本样式（如 .prose）
  presetWind3,           // Tailwind 风格预设：模拟 Tailwind CSS v3 的原子类名系统
  transformerDirectives, // 转换器：支持在 CSS 中使用 /* @apply */ 指令
  transformerVariantGroup, // 转换器：支持在模板中写 hover:(bg-blue text-white) 分组变体
} from 'unocss'
import { createRequire } from 'node:module'

// CJS require 读取图标集合 JSON: Node 22 下 ESM JSON import 必须携带
// `with { type: 'json' }` 属性, 而 presetIcons 默认加载器未携带, 会导致
// 全站 i-ep-* 图标静默失效(不生成任何 CSS), 故显式指定集合加载器
const require = createRequire(import.meta.url)

// 导出 UnoCSS 配置
export default defineConfig({
  // 配置使用的预设（Presets），决定支持哪些类名语法和功能
  presets: [
    presetWind3(),           // 使用类 Tailwind 的实用类，如 flex, p-4, text-lg
    presetAttributify(),     // 启用属性化语法，如 bg="blue-500 hover:blue-400" border="2 rounded"
    presetIcons({ // 图标预设
      scale: 3, // 图标缩放比例
      warn: true, // 控制台输出警告信息
      // 显式集合加载器(见文件头注释): ep 为 Element Plus 图标集
      collections: {
        ep: () => require('@iconify-json/ep/icons.json'),
        'vscode-icons': () => require('@iconify-json/vscode-icons/icons.json'),
      },
    }),           // 启用图标支持，自动将 i-xxx-xxx 转换为 SVG 或 background 图标
    presetTypography(),      // 启用排版样式，为 <article> 等内容区域提供美观的默认样式
  ],

  // 配置转换器（Transformers），用于增强类名的书写方式
  transformers: [
    transformerDirectives(), // 允许在 CSS 或 SFC 的 style 中使用 /* @apply btn */ 语法
    transformerVariantGroup() // 支持分组写法，如 md:(p-2 text-lg) 等价于多个类组合
  ],
  theme: {
    // note 色系注册为原生颜色: 让 bg-note-soft/70、text-note-sub/60、!bg-note-green
    // 这类「shortcut + 透明度/important」写法走 color 规则生效(shortcut 不支持修饰符)
    colors: {
      note: {
        DEFAULT: 'var(--note-border)',
        paper: 'var(--note-paper)',
        soft: 'var(--note-soft)',
        card: 'var(--note-card)',
        tint: 'var(--note-tint)',
        text: 'var(--note-text)',
        sub: 'var(--note-sub)',
        green: 'var(--note-green)',
        deep: 'var(--note-green-deep)',
        accent: 'var(--note-accent)',
        glass: 'var(--note-glass)',
        glow: 'var(--note-glow)',
        edge: 'var(--note-edge-soft)',
        ink: 'var(--note-ink)',
        seal: 'var(--note-seal)',
        water: 'var(--note-water)',
        lotus: 'var(--note-lotus)',
        'border-green': 'var(--note-border-green)',
      },
    },
    animation: {
      keyframes: {
        // 光标闪烁动画
        blink: '{0%,50%{opacity:1}51%,100%{opacity:0}}',
      },
      durations: {
        blink: '1s',
      },
      counts: {
        blink: 'infinite',
      },
    },
    // 语义圆角刻度(与 base.css 全局主题化的组件圆角对齐)
    // 整体收紧一档: 利落书卷气, 大圆角仅保留给对话框/大纸片
    borderRadius: {
      'note-sm': '6px',   // 输入框/按钮/小元素
      'note-md': '10px',  // 卡片/表格
      'note-lg': '14px',  // 对话框/抽屉/Hero
    },
    // 手写体: 用于 Hero 标语/空状态文案等点缀(正文字体保持系统栈)
    fontFamily: {
      hand: 'var(--note-font-hand)',
    },
  },
  rules: [
    // note 色系 + /透明度: var() 颜色无法直接叠 alpha, 用 color-mix 显式混入透明度。
    // 命中此规则时不再走 theme 色规则(值一致, 但此处额外支持了 /NN 修饰)
    [/^(bg|text|border)-note(?:-([\w-]+))?(?:\/(\d{1,3}))?$/, ([, prop, name, alpha]) => {
      const propMap = { bg: 'background-color', text: 'color', border: 'border-color' }
      const varName = name === 'deep'
        ? '--note-green-deep'
        : name === 'border-green'
          ? '--note-border-green'
          : name
            ? `--note-${name}`
            : '--note-border'
      const color = alpha
        ? `color-mix(in srgb, var(${varName}) ${alpha}%, transparent)`
        : `var(${varName})`
      return { [propMap[prop]]: color }
    }] as any,
    // 抽屉
    ['m-1', { margin: '0.3rem' }],
    ['grid-center', { 'grid-template-rows': 'auto minmax(0, 1fr) auto' }],
    ['text-align-last-justify', { 'text-align-last': 'justify' }],
    // 文本溢出省略
    ['text-ellipsis', { overflow: 'hidden', 'text-overflow': 'ellipsis', 'white-space': 'nowrap' }],
    // 隐藏滚动条 -ms-overflow-style 兼容IE10+
    ['scrollbar-hide', { 'scrollbar-width': 'none', '-ms-overflow-style': 'none' }],
    // 渐变背景
    ['bg-gradient-primary', {
      'background-image': 'linear-gradient(135deg, var(--c-primary), var(--c-primary-light))'
    }],
  ],
  shortcuts: [
    // ===== 布局类 =====
    {
      'center': 'flex justify-center items-center',
      'full-flex': 'absolute w-full h-full flex',
      // 居中
      'position-center': 'absolute top-0 left-0 right-0 bottom-0  m-auto',
      'flex-center': 'flex items-center justify-center',
      // 水平居中分开两边
      'mini-text-center-between': 'flex items-center justify-between',
      // 主页三段布局
      'grid-head-center-foot': 'min-h-full grid grid-center',
      // 应用页高度: 视口减去吸顶导航(h-14移动 / h-16桌面)
      'h-app': 'h-[calc(100vh-3.5rem)] md:h-[calc(100vh-4rem)]',
      'max-h-app': 'max-h-[calc(100vh-3.5rem)] md:max-h-[calc(100vh-4rem)]'
    },
    // ===== 淡绿色自然笔记风 =====
    // 取值唯一来源: base.css 中的 --note-* CSS 变量(亮暗自动切换)
    // 此处一律引用变量, 不再写死 hex, 也不需要 dark: 变体
    {
      // 纸张底色(米白/暗色墨绿底)
      'bg-note-paper': 'bg-[var(--note-paper)]',
      // 淡绿软底(侧边栏/卡片内衬)
      'bg-note-soft': 'bg-[var(--note-soft)]',
      // 卡片白(纸片)
      'bg-note-card': 'bg-[var(--note-card)]',
      // 淡绿强调底
      'bg-note-tint': 'bg-[var(--note-tint)]',
      // 文字: 深绿灰主文字
      'text-note': 'text-[var(--note-text)]',
      // 文字: 次级淡绿灰
      'text-note-sub': 'text-[var(--note-sub)]',
      // 文字: 苔绿强调
      'text-note-green': 'text-[var(--note-accent)]',
      // 底色: 苔绿实底(按钮)
      'bg-note-green': 'bg-[var(--note-green)]',
      // 边框: 苔绿强调
      'border-note-green': 'border-[var(--note-border-green)]',
      // 边框: 淡绿灰
      'border-note': 'border-[var(--note-border)]',
      // 阴影: 柔和纸片影(暗色下由变量切换为深色影, 保持层次)
      'shadow-note': 'shadow-[var(--note-shadow)]',
      // 阴影: 悬浮抬升影(配 hover:-translate-y-0.5 + note-transition)
      'shadow-note-hover': 'shadow-[var(--note-shadow-hover)]',
      // 统一交互动效: 时长/缓动全站一致
      'note-transition': 'transition-all duration-200 ease-out',
      // 苔绿渐变(hero用)
      'bg-note-gradient': 'bg-gradient-to-br from-[var(--note-grad-from)] via-[var(--note-grad-via)] to-[var(--note-grad-to)]',
      // 毛玻璃纸底(吸顶头部用; 须配 backdrop-blur-md)
      'bg-note-glass': 'bg-[var(--note-glass)]',
      // 手账虚线分隔线
      'note-dashed-divider': 'border-t border-dashed border-note',
      // 朱砂闲章: 手写体单字小印, 微斜如手钤纸面(原 base.css 全局类 UnoCSS 化)
      'note-seal': 'inline-flex items-center justify-center shrink-0 w-[1.9rem] h-[1.9rem] rounded-md bg-[var(--note-seal)] text-[#f8f1e6] font-hand text-[1.05rem] leading-none -rotate-5 shadow-[0_1px_3px_rgba(0,0,0,0.18)] opacity-92',
      // 胶带贴纸标签(空状态/卡片角标点缀)
      'note-sticker-tag': 'inline-flex items-center px-2 py-0.5 rounded-md bg-note-tint text-note-green text-xs border border-dashed border-note-green',
      // 页面根容器(视口内边距, 移动/桌面双档)
      'page-shell': 'p-4 md:p-6 w-full',
      // 悬浮抬升卡片: 柔光晕 + 轻浮起(卡片/面板 hover 常用组合)
      'note-card-hover': 'note-glow-hover hover:-translate-y-0.5',
      // 书签式不对称圆角: 上方收圆、下方近直角(页签/角标/书签卡)
      'note-bookmark': 'rounded-t-note-md rounded-b-sm',
      // 印章式不对称圆角: 对角圆对角直(徽标/闲章底/装饰块), 手钤纸面的歪斜感
      'note-stamp': 'rounded-tl-md rounded-tr-sm rounded-br-md rounded-bl-sm',
      // 图标工具按钮(图表/面板工具栏通用): 28px 方寸 + 淡绿悬浮
      'note-icon-btn':
        'inline-flex items-center justify-center min-w-7 h-7 px-1.5 rounded-note-sm border-none bg-transparent text-note-sub cursor-pointer text-sm note-transition hover:bg-note-tint hover:text-note-green',
      // 卡片容器(表格/面板通用): 无边线纸片 —— 边缘由 bg-note-card 色差 +
      // shadow-note 内的 1px 光晕环定义; 纸纤维顶盖由 base.css 的 .page-card::after
      // 统一承载, 与 el-card 质感一致
      'page-card': 'p-4 rounded-lg bg-note-card shadow-note',
      // 卡片标题行(标题+右侧操作按钮)
      'card-toolbar': 'mb-3 flex flex-wrap items-center justify-between gap-2',
    },
  ]
})
