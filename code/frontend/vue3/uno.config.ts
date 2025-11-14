import {
  defineConfig,
  presetAttributify,     // 属性化模式预设：支持用 HTML 属性风格写样式，如 text="red lg"
  presetIcons,           // 图标预设：支持使用类名引入图标，如 i-mdi-home
  presetTypography,      // 排版预设：提供文章友好的默认文本样式（如 .prose）
  presetWind3,           // Tailwind 风格预设：模拟 Tailwind CSS v3 的原子类名系统
  transformerDirectives, // 转换器：支持在 CSS 中使用 /* @apply */ 指令
  transformerVariantGroup, // 转换器：支持组合变体语法，如 hover:(bg-blue text-white)
} from 'unocss'

// 导出 UnoCSS 配置
export default defineConfig({
  // 配置使用的预设（Presets），决定支持哪些类名语法和功能
  presets: [
    presetWind3(),           // 使用类 Tailwind 的实用类，如 flex, p-4, text-lg
    presetAttributify(),     // 启用属性化语法，如 bg="blue-500 hover:blue-400" border="2 rounded"
    presetIcons({ // 图标预设
      scale: 3, // 图标缩放比例
      warn: true, // 控制台输出警告信息
    }),           // 启用图标支持，自动将 i-xxx-xxx 转换为 SVG 或 background 图标
    presetTypography(),      // 启用排版样式，为 <article> 等内容区域提供美观的默认样式
  ],

  // 配置转换器（Transformers），用于增强类名的书写方式
  transformers: [
    transformerDirectives(), // 允许在 CSS 或 SFC 的 style 中使用 /* @apply btn */ 语法
    transformerVariantGroup() // 支持分组写法，如 md:(p-2 text-lg) 等价于多个类组合
  ],
  rules: [
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
      'grid-head-center-foot': 'min-h-full grid grid-center'
    },
     // 背景文字颜色
     [
      /^bg-deep-(\d+)$/,
      ([, d]) =>
        `bg-gray-${+d == 0 ? 50 : +d * 100} dark:bg-gray-${+d == 0 ? 950 : 1000 - +d * 100} text-deep-${d}`
    ],
    // 文字颜色  'text-deep-0': 'text-gray-950 dark:text-gray-50', 'text-deep-1': 'text-gray-900 dark:text-gray-100',
    [
      /^text-deep-(\d+)$/,
      ([, d]) =>
        `text-gray-${+d == 0 ? 950 : 1000 - +d * 100} dark:text-gray-${+d == 0 ? 50 : +d * 100}`
    ],
    // btn
    [
      /^btn-deep-(\d+)$/,
      ([, d]) => `px-4 py-1 rounded pointer-default bg-deep-${d} hover:bg-deep-${+d + 1} `
    ]
  ]
})