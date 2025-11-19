// uno.config.js
import { defineConfig, presetWind, presetIcons } from 'unocss'

export default defineConfig({
  presets: [
    presetWind(), // 使用 presetWind 替代 presetUno
    presetIcons({
      collections: {
        // 可配置图标集
      }
    })
  ],
  shortcuts: [
    ['btn', 'px-4 py-2 rounded inline-block bg-teal-600 text-white cursor-pointer hover:bg-teal-700'],
  ],
  rules: [
    // 自定义规则
  ]
})