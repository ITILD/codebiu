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
import { createProxy } from './build/vite/proxy'; // 代理
import { killPort } from './build/vite/kill_port';
// https://vite.dev/config/
export default defineConfig(
  ({ mode }) => {
    const env = loadEnv(mode, process.cwd(), '');
    // console.log('test_', env.VITE_PORT)
    // killPort(env.VITE_PORT)

    const proxys = createProxy(JSON.parse(env.VITE_PROXY as string) as string[][])
    return {
      // 设置基础路径
      base: env.BASE_URL,
      plugins: [
        VueRouter({}),
        vue(),
        vueDevTools(),
        UnoCSS(),
        AutoImport({
          // 自动导入 Vue 相关函数，如：ref, reactive, toRef 等
          imports: ['vue', VueRouterAutoImports, 'pinia'],
          // composition API 函数（例如 ElMessage, ElLoading
          resolvers: [ElementPlusResolver()

          ],
          dts: path.resolve(pathSrc, 'auto-imports.d.ts')
        }),
        Components({
          resolvers: [
            // https://icones.netlify.app/ 自动注册图标组件“前缀-使用的图标库名称-图标名”  <i-ep-edit />
            IconsResolver({
              // prefix: 'Icon', // 修改前缀 默认 i
              enabledCollections: ['ep'] // 指定需要自动导入的图标库
            }),
            //自动导入 Element Plus 组件
            ElementPlusResolver()
          ],
          dts: path.resolve(pathSrc, 'components.d.ts') // 组件类型声明文件位置
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
    }
  })

