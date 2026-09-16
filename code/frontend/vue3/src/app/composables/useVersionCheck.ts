/**
 * 前端版本检测组合式函数:
 * 打包时 vite.config.ts 从 package.json 读取版本号注入 __APP_VERSION__,
 * 并在构建产物根目录生成 version.json; 此处轮询服务器上的 version.json
 * 与本地编译版本比对, 不一致即置 hasNewVersion(顶栏按钮提示, 非弹窗)
 */
import { ref, onMounted, onUnmounted } from 'vue'

/** 轮询间隔: 60 分钟 */
const POLL_INTERVAL = 60 * 60 * 1000

/** sessionStorage 标记: chunk 加载失败自动刷新只允许执行一次, 防止死循环 */
const AUTO_RELOAD_FLAG = 'app:auto_reload_for_chunk'

/** chunk 加载失败(发新版后旧页面引用的 js 已被删除)时静默自动刷新一次 */
function setupChunkErrorReload(): void {
  // vite 资源预加载失败事件
  window.addEventListener('vite:preloadError', () => {
    if (sessionStorage.getItem(AUTO_RELOAD_FLAG)) return
    sessionStorage.setItem(AUTO_RELOAD_FLAG, '1')
    window.location.reload()
  })
  // 动态 import 失败兜底(路由懒加载 chunk 已被删除)
  window.addEventListener('unhandledrejection', (e) => {
    const msg = String((e.reason as Error)?.message ?? e.reason ?? '')
    if (
      /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module/i.test(msg) &&
      !sessionStorage.getItem(AUTO_RELOAD_FLAG)
    ) {
      sessionStorage.setItem(AUTO_RELOAD_FLAG, '1')
      window.location.reload()
    }
  })
}

export function useVersionCheck() {
  /** 服务器版本比当前编译版本新时为 true(顶栏显示"版本已发布点击刷新") */
  const hasNewVersion = ref(false)

  /** 拉取服务器 version.json(带时间戳防 nginx/浏览器缓存)并比对 */
  const check = async () => {
    // 开发环境无 version.json(仅构建产物含), 跳过检测避免控制台网络报错噪音
    if (import.meta.env.DEV) return
    try {
      const res = await fetch(
        `${import.meta.env.BASE_URL}version.json?t=${Date.now()}`,
        { cache: 'no-store' },
      )
      if (!res.ok) return
      const data = (await res.json()) as { version?: string }
      hasNewVersion.value = Boolean(data.version && data.version !== __APP_VERSION__)
    } catch {
      // 开发环境无 version.json 或网络异常: 静默忽略, 不打断使用
    }
  }

  /** 页面重新可见时立即检测一次(用户切回标签页即可感知新版本) */
  const onVisible = () => {
    if (document.visibilityState === 'visible') check()
  }

  // 轮询 + 标签页重新可见/窗口聚焦时检测; 组件卸载时清理定时器与监听
  let timer: ReturnType<typeof setInterval> | null = null
  onMounted(() => {
    check()
    setupChunkErrorReload()
    timer = setInterval(check, POLL_INTERVAL)
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('focus', check)
  })
  onUnmounted(() => {
    if (timer) clearInterval(timer)
    document.removeEventListener('visibilitychange', onVisible)
    window.removeEventListener('focus', check)
  })

  return { hasNewVersion, check }
}
