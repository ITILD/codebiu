import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate';
import App from './App.vue'
import router from './router'
/* 
「reset 必须最先加载」同等特异性下源顺序会决定胜负，行为不可预测
*/
import '@unocss/reset/tailwind.css'// 重置边距 margin等0
import 'virtual:uno.css'
// /*
// 一旦显式 import 'element-plus/dist/index.css' 
// vite.config.ts 里的 ElementPlusResolver({ importStyle: 'css' })
//  改成 ElementPlusResolver() （不带 importStyle ），否则样式会被重复引入。
// */
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css' // 引入element暗黑主题
import { i18n } from '@/i18n/language'
const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
pinia.use(piniaPluginPersistedstate)
app.use(router)
app.use(i18n)
app.mount('#app')
