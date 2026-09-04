/**
 * 全局系统设置状态:主题(明暗)、布局(侧边栏/头部开关)、响应式断点、语言等。
 * 通过 useDark 与 localStorage 联动实现主题持久化。
 */
import { useDark, useBreakpoints } from '@vueuse/core'

const SysSettingStore = defineStore('sysSetting', () => {
  // 项目断点(与 UnoCSS presetWind3 的 md/lg 前缀对齐):
  // 手机 <768 / 平板 768-1023 / 桌面 >=1024
  const breakpoints = useBreakpoints({ md: 768, lg: 1024 })
  const baseMd = 768
  const sysStyle = ref({
    headFootShow: true,
    isUserControlShow: false,
    // 左侧选择栏
    leftControlShow: true,
    // 移动端侧边栏抽屉开关
    isSidebarDrawerOpen: false,
    // 平板及以上(>=768, 与 CSS md: 类的 min-width:768px 对齐): 控制侧边栏显隐/汉堡按钮
    isMd: breakpoints.greater('md'),
    // 桌面及以上(>=1024): 控制侧边栏默认展开(平板默认折叠)
    isLg: breakpoints.greater('lg'),
    theme: {
      isDark: useDark(),
      // useDark 本地设置 auto light dark
      themeValue: localStorage.getItem('vueuse-color-scheme'),
      head: [{ height: '35px' }],
      leftControl: {
        tabPosition: 'left'
      }
    },
    language: 'zh' as any
  })

  const sysObj = {
    $ObjLargeTemp: new Map()
  }
  // isMd/isLg 由 useBreakpoints 响应式监听窗口变化驱动(替代原 window.onresize 全局赋值)
  // 设置弹窗显隐
  const isSysSettingShow = ref(false)
  // 根据主题值更改isDark(light/dark/auto 三态切换)
  const changeIsDarkByThemeValue = () => {
    switch (sysStyle.value.theme.themeValue) {
      case 'light':
        sysStyle.value.theme.isDark = false
        break
      case 'dark':
        sysStyle.value.theme.isDark = true
        break
      case 'auto':
        // 媒体查询检测夜晚/黑暗模式
        sysStyle.value.theme.isDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
        break
    }
    return sysStyle.value.theme.isDark
  }
  // 根据isDark更改主题(写入 localStorage 供 useDark 恢复)
  const changeThemeValueByIsDark = () => sysStyle.value.theme.themeValue = sysStyle.value.theme.isDark ? 'dark' : 'light'

  return { sysStyle, sysObj, isSysSettingShow, changeIsDarkByThemeValue, changeThemeValueByIsDark }
})

export { SysSettingStore }
