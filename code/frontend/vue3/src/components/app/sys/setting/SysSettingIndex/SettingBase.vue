<template>
    <div p-2>
    <!-- 黑白主题 -->
    <BaseSelect
      w-70
      h-14
      m-2
      v-model="sysSettingStore.sysStyle.theme.themeValue"
      :name="$t('theme')"
      :options="themeOptions"
      :changeValueFunc="sysSettingStore.changeIsDarkByThemeValue"
    />
    <!-- 语言选择 -->
    <SettingLanguage w-70 h-14 m-2 />
  </div>
</template>

<script setup lang="ts">
// import { storeToRefs } from 'pinia'
import { SysSettingStore } from '@/stores/sys'
import { i18n, languageOptions } from '@/i18n/language'
const sysSettingStore = SysSettingStore()
/////////////////////////////////////////////////////////主题控制/////////////////////////////////////////////////////////
// 全局主题
// 主题选择
const themeOptions = ref([
  {
    value: 'light',
    label: computed(() => i18n.global.t('light'))
  },
  {
    value: 'dark',
    label: computed(() => i18n.global.t('dark'))
  },
  {
    value: 'auto',
    label: computed(() => i18n.global.t('autoSys'))
  }
])

/////////////////////////////////////////////////////////todo/////////////////////////////////////////////////////////
</script>
<style scoped></style>
