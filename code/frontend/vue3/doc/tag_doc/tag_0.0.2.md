# 添加基础开发组件

考虑引入unocss elemnet-plus unplugin-vue-router

## 1. 添加自动路由插件

添加自动路由插件unplugin-vue-router，写页面文件生成对应路由

官方文档：https://uvr.esm.is/introduction.html

```sh
pnpm install -D unplugin-vue-router
```

vite.config.ts 打包工具添加插件

```diff
+ import VueRouter from 'unplugin-vue-router/vite' 自动引入路由
  export default defineConfig({
    plugins: [
+    VueRouter({}),
      Vue(),
    ],
  })
```

tsconfig.app.json 类型添加

```diff
{
  "include": [
    // other files...
+   "./typed-router.d.ts"
  ],
  "compilerOptions": {
    // ...
    "moduleResolution": "Bundler",
    // ...
  }
}
```

env.d.ts 添加路由类型

```diff
+ /// <reference types="unplugin-vue-router/client" />
```

迁移现有项目

```diff
import { createRouter, createWebHistory } from 'vue-router'
- import HomeView from '../views/HomeView.vue'
+ import { routes, handleHotUpdate } from 'vue-router/auto-routes'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
- routes: [
-   {
-     path: '/',
-     name: 'home',
-     component: HomeView,
-    },
-    {
-      path: '/about',
-      name: 'about',
-      // route level code-splitting
-      // this generates a separate chunk (About.[hash].js) for this route
-      // which is lazy-loaded when the route is visited.
-      component: () => import('../views/AboutView.vue'),
-    },
-  ],
+ routes: routes
})
+ //开发热更新路由
+ if (import.meta.hot) {
+   handleHotUpdate(router)
+ }

export default router

```

文件/文件夹重命名

```sh
mv src/views src/pages
mv src/pages/index.vue src/pages/index.vue
```

src\App.vue 修改内容,点击调准使用自动路由

```diff
- <RouterLink to="/about">About</RouterLink>
+ <RouterLink to="/AboutView">About</RouterLink>
```

## 2. 添加自动引入vue库/自定义组件/element-plus库配置

自动引入api  ，unplugin-auto-import
官方文档：https://github.com/antfu/unplugin-auto-import  
自动引入组件unplugin-vue-components
官方文档：https://github.com/antfu/unplugin-vue-components

```sh
pnpm install -D unplugin-auto-import unplugin-vue-components
pnpm install element-plus
```

vite.config.ts 打包工具添加自动引入插件

```diff
+ import AutoImport from 'unplugin-auto-import/vite' //自动导入 API
+ import Components from 'unplugin-vue-components/vite'//自动导入组件
+ import { ElementPlusResolver } from 'unplugin-vue-components/resolvers' //自动引入element-plus组件
+ import { VueRouterAutoImports } from 'unplugin-vue-router'
+ // 代码根路径
+ import path from 'path'
+ const pathSrc = path.resolve(__dirname, 'src')
  export default defineConfig({
    plugins: [
+     AutoImport({
+       // 自动导入 Vue 相关函数，如：ref, reactive, toRef 等
+       imports: ['vue', VueRouterAutoImports, 'pinia'],
+       // composition API 函数（例如 ElMessage, ElLoading
+       resolvers: [ElementPlusResolver(),],
+       dts: path.resolve(pathSrc, 'auto-imports.d.ts')
+     }),
+     Components({
+       resolvers: [
+         //自动导入 Element Plus 组件
+         ElementPlusResolver(),
+       ],
+       dts: path.resolve(pathSrc, 'components.d.ts') // 组件类型声明文件位置
+     })
    ],
  })
```

.gitignore 忽略文件

```diff
+ # 插件 插件自动引入的类型文件
+ auto-imports.d.ts
+ components.d.ts
```

src\pages\index.vue 测试自动引入TheWelcome.vue组件
```diff
- import TheWelcome from '../components/TheWelcome.vue'
```
src\main.ts 引入element-plus主题
```diff
+ import 'element-plus/theme-chalk/dark/css-vars.css' // 引入element暗黑主题
```

src\pages\AboutView.vue 测试自动引入element-plus组件
```diff
<template>
  <div>
    <h1>This is an about page</h1>
+    <el-button type="primary" @click="showMessage">点测试自动引入</el-button>
  </div>
</template>
+ <script setup lang="ts">
+ // 测试自动引入
+ const showMessage = () => {
+  ElMessage.success('自动引入Element Plus 成功！')
+ }
+ </script>
```


## 3. 添加unocss+tailwindcss样式规则

unocss 是一个原子css库，可以自动生成css样式，不需要手动编写css样式，可以减少css代码量，提高开发效率，同时也可以提高代码的可维护性。  
官方文档：https://unocss.dev/guide/
在线测试：https://unocss.dev/interactive/
编译后css的文件:http://localhost:5173/__unocss#/
```sh
pnpm install -D unocss
pnpm add @unocss/reset
```

vite.config.ts 打包工具添加unocss插件
```diff
import { VueRouterAutoImports } from 'unplugin-vue-router'
+ import UnoCSS from 'unocss/vite'// css 辅助
export default defineConfig({
  plugins: [
    ...
    vueDevTools(),
+    UnoCSS(),
```
src\main.ts 添加配置
```diff
+ import 'virtual:uno.css'
+ import '@unocss/reset/tailwind.css'// 重置边距 margin等0
```
根目录创建uno.config.ts
```diff
+ 添加配置
```
## 4. 添加图标插件
图标参考：https://icones.netlify.app
```sh
pnpm install -D unplugin-icons @iconify-json/ep @iconify-json/vscode-icons
```
vite.config.ts 打包工具添加unocss插件,添加后直接使用 **<i-图标库名-图标名>**可以直接下载引用
```diff
+ import Icons from 'unplugin-icons/vite'//图标
+ import IconsResolver from 'unplugin-icons/resolver' //图标插件
...
    Components({
+      resolvers: [
+        // https://icones.netlify.app/ 自动注册图标组件“前缀-使用的图标库名称-图标名”  <i-ep-edit />
+        IconsResolver({ 
+          // prefix: 'Icon', // 修改前缀 默认 i
+        }),
        //自动导入 Element Plus 组件
        ElementPlusResolver()
      ],
      dts: path.resolve(pathSrc, 'components.d.ts') // 组件类型声明文件位置
    }),
+    Icons({ autoInstall: true }), //自动下载图标库,必须在 Components 之后或独立存在
```

## 5. 添加基础端口



## 6.添加首页和基础页面
- 添加图标