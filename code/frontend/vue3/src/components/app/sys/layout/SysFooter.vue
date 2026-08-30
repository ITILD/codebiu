<template>
  <footer v-if="sysStyle.headFootShow" border-t border-note>
    <!-- 关联账号 本站 备案 -->
    <div flex flex-col items-center gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-0>
      <!-- 关联账号 -->
      <div flex space-x-6 text-note-sub>
        <a v-for="link in socialLinks" :key="link.name" :href="link.url" text-note-green hover:opacity-70>
          <component :is="link.icon" h-5 w-5 />
          <span sr-only>{{ link.name }}</span>
        </a>
      </div>
      <!-- 年份提示 + 备案(合并为一组,移动端居中堆叠,避免长文本截断) -->
      <div flex flex-col items-center gap-1 text-center sm:flex-row sm:gap-6 text-note-sub>
        <span text-xs md:text-sm>© 2023-{{ yearNow }} <a href="https://wx1s.com/"
            hover:underline>ITILD</a>. All Rights Reserved.</span>
        <span text-xs hover:underline>© 备案号: <a href="https://beian.miit.gov.cn/"
            target="_blank">辽ICP备2022000388号-1</a></span>
      </div>
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
