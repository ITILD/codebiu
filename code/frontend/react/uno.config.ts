// uno.config.js
import {
  defineConfig,
  presetAttributify,     // 属性化模式预设：支持用 HTML 属性风格写样式，如 text="red lg"
  presetIcons,           // 图标预设：支持使用类名引入图标，如 i-mdi-home
  presetTypography,      // 排版预设：提供文章友好的默认文本样式（如 .prose）
  presetWind3,           // Tailwind 风格预设：模拟 Tailwind CSS v3 的原子类名系统
  transformerDirectives, // 转换器：支持在 CSS 中使用 /* @apply */ 指令
  transformerVariantGroup, // 转换器：支持组合变体语法，如 hover:(bg-blue text-white)
} from 'unocss'
export default defineConfig({
  presets: [
    presetWind3(),           // 使用类 Tailwind 的实用类，如 flex, p-4, text-lg
    presetAttributify(),     // 启用属性化语法，如 bg="blue-500 hover:blue-400" border="2 rounded"
    presetIcons({ // 图标预设
      scale: 3, // 图标缩放比例
      warn: true, // 控制台输出警告信息
    }),           // 启用图标支持，自动将 i-xxx-xxx 转换为 SVG 或 background 图标
    presetTypography(),      // 启用排版样式，为 <article> 等内容区域提供美观的默认样式
  ],
  shortcuts: [
    ['btn', 'px-4 py-2 rounded inline-block bg-teal-600 text-white cursor-pointer hover:bg-teal-700'],
  ],
  rules: [
    // 自定义规则
  ]
})