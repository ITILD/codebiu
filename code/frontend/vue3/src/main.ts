import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import 'virtual:uno.css'
import '@unocss/reset/tailwind.css'// 重置边距 margin等0
import 'element-plus/theme-chalk/dark/css-vars.css' // 引入element暗黑主题
import { i18n } from '@/i18n/language'
const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(i18n)
app.mount('#app')
