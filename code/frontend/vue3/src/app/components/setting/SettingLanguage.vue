<template>
  <!-- 语言选择 -->
  <div flex items-center gap-2 p-1>
    <span w-20 shrink-0>{{ $t('language') }}</span>
    <el-select v-model="sysStyle.language" @change="changeValueFunc">
      <el-option
        v-for="item in languageOptions"
        :key="item.value"
        :label="item.label"
        :value="item.value"
      />
    </el-select>
  </div>
</template>

<script setup lang="ts">
import { SysSettingStore } from '@/stores/sys'
import { i18n, languageOptions } from '@/i18n/language'
const { sysStyle } = SysSettingStore()
/////////////////////////////////////////////////////////todo/////////////////////////////////////////////////////////
const changeValueFunc = () => (i18n.global.locale = sysStyle.language)
</script>
