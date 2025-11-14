<template>
  <footer v-if="sysStyle.headFootShow">
    <!-- <hr border-gray-400 sm:mx-auto dark:border-gray-8 lg:mb-2 /> -->
    <!-- 关联账号 本站 备案 -->
    <div sm:flex sm:items-center sm:justify-between>
      <!-- 关联账号 -->
      <div text-gray-500 flex mt-4 space-x-6 sm:justify-center sm:mt-0>
        <a v-for="link in socialLinks" :key="link.name" :href="link.url" text-deep-5 hover:text-deep-3>
          <component :is="link.icon" h-5 w-5 />
          <span sr-only>{{ link.name }}</span>
        </a>
      </div>
      <!-- 年份提示 -->
      <span text-sm text-gray-500 sm:text-center dark:text-gray-400>© 2023-{{ yearNow }} <a href="https://wx1s.com/"
          hover:underline>ITILD</a>. All Rights
        Reserved.<br />
      </span>
      <!-- 备案 -->
      <span text-xs text-gray-500 sm:text-center dark:text-gray-400 hover:underline>© 备案号: <a
          href="https://beian.miit.gov.cn/" target="_blank">辽ICP备2022000388号-1</a>
      </span>
    </div>
  </footer>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import GmailSVG from '@/components/miniUI/miniSvg/GmailSVG.vue'
import GithubSVG from '@/components/miniUI/miniSvg/GithubSVG.vue'
import DribbbleSVG from '@/components/miniUI/miniSvg/DribbbleSVG.vue'

// 样式控制
import { SysSettingStore } from '@/stores/sys'
const sysSettingStore = SysSettingStore()
const sysStyle = sysSettingStore.sysStyle

const yearNow = ref(new Date().getFullYear())

const socialLinks = [
  { name: 'Gmail', url: '#', icon: GmailSVG },
  { name: 'GitHub', url: '#', icon: GithubSVG },
  { name: 'Dribbble', url: '#', icon: DribbbleSVG }
]
</script>
