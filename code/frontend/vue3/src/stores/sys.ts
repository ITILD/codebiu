import { useDark } from '@vueuse/core'
const SysSettingStore = defineStore('sysSetting', () => {
  // state
  const baseMd = 768
  const sysStyle = ref({
    headFootShow: true,
    isUserControlShow: false,
    // 左侧选择栏
    leftControlShow: true,
    // 大小屏切分 普通页面不需要考虑横屏，部分三维场景考虑
    isMd: window.innerWidth > baseMd,
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
  // 窗口变化重置 // 判断中小设备
  window.onresize = () => sysStyle.value.isMd = window.innerWidth > baseMd
  // 设置弹窗
  const isSysSettingShow = ref(false)
  // 根据主题值更改isDark
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
  // 根据isDark更改主题
  const changeThemeValueByIsDark = () => sysStyle.value.theme.themeValue = sysStyle.value.theme.isDark ? 'dark' : 'light'
 
  return { sysStyle, sysObj, isSysSettingShow, changeIsDarkByThemeValue, changeThemeValueByIsDark }
})

export { SysSettingStore }
