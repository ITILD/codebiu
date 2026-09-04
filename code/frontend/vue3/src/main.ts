import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate';
import App from './App.vue'
import router from './router'
/* 
「reset 必须最先加载」同等特异性下源顺序会决定胜负，行为不可预测
*/
import '@unocss/reset/tailwind.css'// 重置边距 margin等0
// /*
// 一旦显式 import 'element-plus/dist/index.css' 
// vite.config.ts 里的 ElementPlusResolver({ importStyle: 'css' })
//  改成 ElementPlusResolver() （不带 importStyle ），否则样式会被重复引入。
// */
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css' // 引入element暗黑主题
// 自定义主题(含 :root / html.dark 变量与组件微调)必须在 element-plus 样式之后加载,
// 否则同特异性下 element 的默认变量(灰底/蓝色主色)会覆盖掉墨绿自然笔记主题
import './assets/main.css'
import 'virtual:uno.css'
import { i18n } from '@/common/i18n/language'
const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
pinia.use(piniaPluginPersistedstate)
app.use(router)
app.use(i18n)
app.mount('#app')
