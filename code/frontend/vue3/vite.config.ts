import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
// 开发插件
import VueRouter from 'unplugin-vue-router/vite'// 自动引入路由
import AutoImport from 'unplugin-auto-import/vite' //自动导入 API
import Components from 'unplugin-vue-components/vite'//自动导入组件
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers';
import { VueRouterAutoImports } from 'unplugin-vue-router'
import UnoCSS from 'unocss/vite'// css 辅助
import Icons from 'unplugin-icons/vite'//图标
import IconsResolver from 'unplugin-icons/resolver' //图标插件
// 代码根路径
import path from 'path'
const pathSrc = path.resolve(__dirname, 'src')
// 代理
import { createProxy } from './tools/vite/proxy'; // 代理
import { killPort } from './tools/vite/kill_port';
// https://vite.dev/config/
export default defineConfig(
  ({ mode }) => {
    const env = loadEnv(mode, process.cwd(), '');
    // console.log('test_', env.VITE_PORT)
    killPort(env.VITE_PORT)

    const proxys = createProxy(JSON.parse(env.VITE_PROXY as string) as string[][])
    return {
      // 设置基础路径
      base: env.BASE_URL,

      // 插件配置
      plugins: [
        vue(),
        // 自动路由(特性/模块化架构):
        // 1. src/pages            —— 全局页面(首页/后台工作台/账户设置/404 等)
        // 2. src/modules/*/pages  —— 各业务模块页面, 按模块规范生成路由 /<模块名>/<页面>,
        //    如 src/modules/authorization/pages/user.vue -> /authorization/user
        //    页面与所在模块的 api/components/types 同目录, 删除模块文件夹即删除整个功能
        VueRouter({
          routesFolder: [
            'src/pages',
            {
              src: 'src/modules',
              filePatterns: '**/pages/**',
              path: (file) => {
                // D:/.../src/modules/<模块>/pages/<页面>.vue -> <模块>/<页面>.vue
                const posixFile = file.replace(/\\/g, '/')
                const rest = posixFile.slice(posixFile.lastIndexOf('src/modules') + 'src/modules'.length + 1)
                return rest.replace('/pages/', '/')
              },
            },
          ],
          // 路由 meta 标记(登录拦截与侧边栏显示的依据):
          // 首页与 404 为公开页, 其余(后台工作台/账户设置/各模块页面)统一标记 admin
          extendRoute: (route) => {
            const file = (route.component ?? '').replace(/\\/g, '/')
            const isPublic = file.endsWith('/src/pages/index.vue') || file.includes('/[..all].vue')
            if (file && !isPublic) route.addToMeta({ admin: true })
            // 全屏页面(如三维地球): 锁定文档滚动, 页面内容占满视口剩余高度
            if (file.endsWith('/modules/geometry/pages/earth.vue')) route.addToMeta({ fullpage: true })
          },
        }),
        vueDevTools(),

        // 辅助导入和设定 tailwindcss 等 css 框架
        UnoCSS(),

        // Auto-import Element Plus APIs (ElMessage, ElNotification, etc.)
        AutoImport({
          // 自动导入 Vue 相关函数，如：ref, reactive, toRef 等
          imports: ['vue', VueRouterAutoImports, 'pinia'],
          // composition API 函数（例如 ElMessage, ElLoading
          resolvers: [ElementPlusResolver()

          ],
          dts: path.resolve(pathSrc, 'auto-imports.d.ts')
        }),

        // Auto-import Element Plus components from templates
        Components({
          // 自动注册全局公共组件(模板中无需 import):
          // src/common/components —— 与业务无关的通用组件(TableSearchBar/chat/ide/icons)
          // src/app/components    —— 应用壳组件(SysHeader/SysSidebar/SysFooter/设置面板)
          // 业务模块私有组件放在 src/modules/*/components, 使用时显式 import
          dirs: ['src/common/components', 'src/app/components'],
          resolvers: [
            // https://icones.netlify.app/ 自动注册图标组件“前缀-使用的图标库名称-图标名”  <i-ep-edit />
            IconsResolver({
              // prefix: 'Icon', // 修改前缀 默认 i
              enabledCollections: ['ep'] // 指定需要自动导入的图标库
            }),
            //自动导入 Element Plus 组件
            ElementPlusResolver(
              // 表示自动导入组件时，同步引入其对应的 CSS 样式文件。
              { importStyle: 'css' })
          ],
          dts: path.resolve(pathSrc, 'components.d.ts'), // 组件类型声明文件位置
          // 排除 MonacoEditor 组件(由页面 defineAsyncComponent 异步加载, 避免打进主包)
          exclude: [/BaseMoacoEdit\.vue$/],
        }),
        Icons({ autoInstall: true }), //自动下载图标库 必须在 Components 之后或独立存在

      ],
      resolve: {
        alias: {
          '@': fileURLToPath(new URL('./src', import.meta.url))
        },
      },

      // 开发服务设置
      server: {
        port: Number(env.VITE_PORT),
        strictPort: true,
        host: '0.0.0.0',
        allowedHosts: true, // 允许所有 Host
        headers: {
          'Access-Control-Allow-Origin': '*'
        },
        // 代理
        proxy: proxys
      },

      // 依赖优化配置
      optimizeDeps: {
        // 显式包含常用依赖，避免运行时动态发现
        // include: [
        //   'element-plus/es',
        //   '@microsoft/fetch-event-source',
        // ]
        // 首次启动时强制预构建所有依赖（启动稍慢，但后续稳定）
        // force: true,
      }
    }
  })

