/**
 * 响应式断点组合式函数: 统一导出 isMd(平板>=768)/isLg(桌面>=1024)
 * 替代各页面重复的 SysSettingStore + computed 三行样板
 */
import { computed } from 'vue'
import { SysSettingStore } from '@/common/stores/sys'

export function useResponsive() {
  const sysSettingStore = SysSettingStore()
  return {
    /** 平板及以上(>=768): 控制表格操作列固定、侧边栏显隐等 */
    isMd: computed(() => sysSettingStore.sysStyle.isMd),
    /** 桌面及以上(>=1024): 控制侧边栏默认展开等 */
    isLg: computed(() => sysSettingStore.sysStyle.isLg),
  }
}
