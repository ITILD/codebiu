import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate';
import App from './App.vue'
import router from './router'
/* 
「reset 必须最先加载」同等特异性下源顺序会决定胜负，行为不可预测
*/
import '@unocss/reset/tailwind.css'// 重置边距 margin等0
// Element Plus 全量基础样式(经 gzip 后体积有限, 且保证 ElMessage/v-loading 等
// 命令式服务样式完整; 组件 JS 本身仍是按需的)
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css' // 暗色模式 CSS 变量(体积小, 随主题常驻)
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
