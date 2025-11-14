<template>
  <!-- 语言选择 -->
  <div flex items-center p-1 rounded-md text-align-last-justify>
    <!-- 对齐key -->
    <div class="w-4/9" flex items-center>
      <span w-full h-full>{{ $t('language') }}</span>
      <span mx-2 h-full>:</span>
    </div>
    <!-- 下拉选择 -->
    <select v-model="sysStyle.language" @change="changeValueFunc" bg-deep-2 class="w-5/9" h-full rounded-md outline-none
      px-4>
      <!-- <option disabled value="">Please select one</option> -->
      <option v-for="item in languageOptions" :key="item.value" :value="item.value" bg-deep-2>
        <!--     :label="item.label" -->
        <!-- <img src="" alt="" w-50 h-50 /> -->
        {{ item.label }}
      </option>
    </select>
  </div>
</template>

<script setup lang="ts">
// import { storeToRefs } from 'pinia'
import { SysSettingStore } from '@/stores/sys'
import { i18n, languageOptions } from '@/i18n/language'
const { sysStyle } = SysSettingStore()
/////////////////////////////////////////////////////////todo/////////////////////////////////////////////////////////
const changeValueFunc = () => (i18n.global.locale = sysStyle.language)
</script>
<style scoped></style>
