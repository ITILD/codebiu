<template>
  <div p-2 flex flex-col gap-2>
    <!-- 黑白主题 -->
    <div flex items-center gap-2>
      <span w-20 shrink-0>{{ $t('theme') }}</span>
      <el-select
        v-model="sysSettingStore.sysStyle.theme.themeValue"
        :placeholder="$t('theme')"
        @change="sysSettingStore.changeIsDarkByThemeValue"
      >
        <el-option
          v-for="option in themeOptions"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
    </div>
    <!-- 语言选择 -->
    <SettingLanguage />
  </div>
</template>

<script setup lang="ts">
import { SysSettingStore } from '@/stores/sys'
import { i18n } from '@/i18n/language'
const sysSettingStore = SysSettingStore()
/////////////////////////////////////////////////////////主题控制/////////////////////////////////////////////////////////
// 主题选择
const themeOptions = computed(() => [
  { value: 'light', label: i18n.global.t('light') },
  { value: 'dark', label: i18n.global.t('dark') },
  { value: 'auto', label: i18n.global.t('autoSys') }
])

/////////////////////////////////////////////////////////todo/////////////////////////////////////////////////////////
</script>
