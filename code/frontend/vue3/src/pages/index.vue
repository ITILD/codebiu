<template>
  <div w-full max-w-5xl mx-auto p-4 md:p-8>
    <!-- Hero: 自然笔记卡片(苔绿渐变+笔记本格线), 登录态感知 -->
    <section
      relative
      overflow-hidden
      rounded-2xl
      border-note
      bg-note-gradient
      p-8
      md:p-14
      mb-10
    >
      <!-- 笔记本横线纹理 -->
      <div absolute inset-0 note-lined-paper pointer-events-none />
      <!-- 右上角叶片装饰 -->
      <div absolute top-4 right-6 text-4xl md:text-5xl opacity-70 dark:opacity-90 select-none>🌿</div>

      <div relative>
        <!-- 已登录: 时段问候 + 实时状态徽章 + 最近访问 -->
        <template v-if="isLoggedIn">
          <h1 font-serif text-3xl md:text-5xl font-bold text-note-green mb-3>
            {{ greeting }}，{{ displayName }}
          </h1>
          <p text-base md:text-lg text-note-sub mb-6 max-w-xl leading-relaxed>
            像打理一页自然笔记一样，安放你的数据与灵感。
          </p>

          <!-- 服务器实时状态徽章(获取失败时整行隐藏, 静默降级) -->
          <div v-if="hardware" flex flex-wrap items-center gap-2 mb-6>
            <span
              v-for="badge in statusBadges"
              :key="badge.label"
              inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-note-card border border-note text-xs md:text-sm text-note shadow-note
            >
              <i w-2 h-2 rounded-full inline-block class="bg-note-green" />
              {{ badge.label }}
              <b text-note-green>{{ badge.value }}</b>
            </span>
          </div>

          <!-- 最近访问快捷入口 -->
          <div v-if="recentPages.length" mb-7>
            <p text-xs text-note-sub mb-2>最近访问</p>
            <div flex flex-wrap gap-2>
              <RouterLink
                v-for="item in recentPages.slice(0, 6)"
                :key="item.path"
                :to="item.path"
                px-3 py-1.5 rounded-full bg-note-card border border-note text-xs md:text-sm text-note hover:border-note-green hover:text-note-green transition-colors
              >
                {{ item.title }}
              </RouterLink>
            </div>
          </div>

          <RouterLink
            to="/admin"
            inline-flex
            items-center
            gap-2
            px-6
            py-2.5
            rounded-full
            bg-note-green
            text-white
            font-medium
            transition-all
            duration-300
            hover:opacity-90
            hover:-translate-y-0.5
            hover:shadow-note
          >
            <el-icon><Promotion /></el-icon>
            进入工作台
          </RouterLink>
        </template>

        <!-- 未登录: 品牌引导 -->
        <template v-else>
          <h1 font-serif text-3xl md:text-5xl font-bold text-note-green mb-4>
            {{ TITLE }}
          </h1>
          <p text-base md:text-lg text-note-sub mb-2 max-w-xl leading-relaxed>
            像打理一页自然笔记一样，安放你的数据与灵感。
          </p>
          <p text-sm md:text-base text-note-sub mb-8 max-w-xl>
            登录后点击右上角头像，即可进入后台管理工作台。
          </p>
          <RouterLink
            to="/admin"
            inline-flex
            items-center
            gap-2
            px-6
            py-2.5
            rounded-full
            bg-note-green
            text-white
            font-medium
            transition-all
            duration-300
            hover:opacity-90
            hover:-translate-y-0.5
            hover:shadow-note
          >
            <el-icon><Promotion /></el-icon>
            进入工作台
          </RouterLink>
        </template>
      </div>
    </section>

    <!-- 功能模块入口卡片(数据源与侧边栏菜单一致, 含权限过滤) -->
    <section>
      <div flex items-center gap-2 mb-6>
        <span text-xl>📖</span>
        <h2 font-serif text-2xl font-semibold text-note>功能模块</h2>
        <div flex-1 border-b border-dashed border-note />
      </div>

      <div grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5>
        <RouterLink
          v-for="module in moduleCards"
          :key="module.index"
          :to="module.target"
          bg-note-card
          border
          border-note
          rounded-xl
          p-6
          transition-all
          duration-300
          hover:-translate-y-1
          hover:shadow-note
          hover:border-note-green
          group
        >
          <div
            flex
            items-center
            justify-center
            w-11
            h-11
            rounded-full
            bg-note-tint
            text-note-green
            mb-4
            transition-transform
            duration-300
            group-hover:scale-110
          >
            <el-icon :size="22"><component :is="module.icon" /></el-icon>
          </div>
          <h3 text-lg font-semibold text-note mb-2>{{ module.title }}</h3>
          <p text-sm text-note-sub leading-relaxed>{{ module.desc }}</p>
        </RouterLink>
      </div>
    </section>

    <!-- 底部小语 -->
    <section mt-12 text-center>
      <p text-sm text-note-sub font-serif italic>
        「 淡淡的绿意，是数据生长的样子 」
      </p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { markRaw, computed, ref, onMounted } from 'vue'
import { Promotion } from '@element-plus/icons-vue'
import type { Component } from 'vue'
import { useAuthStore } from '@/common/stores/auth'
import { useVisibleMenu } from '@/common/composables/useMenu'
import { useRecentPages } from '@/common/composables/useRecentPages'
import { getStatusCache } from '@/modules/main/api/status'
import type { HardwareStatus } from '@/modules/main/types/status'

const TITLE = import.meta.env.VITE_GLOB_APP_TITLE

const authStore = useAuthStore()
const { visibleMenuItems } = useVisibleMenu()
const { recentPages } = useRecentPages()

// ===== 登录态与问候 =====
const isLoggedIn = computed(() => Boolean(authStore.authState.user.id))
const displayName = computed(() => authStore.authState.user.nickname || authStore.authState.user.username)

/** 按当前时段返回问候语 */
function greetingByHour(): string {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
}
const greeting = ref(greetingByHour())

// ===== 服务器实时状态徽章(仅登录后拉取, 失败静默隐藏) =====
const hardware = ref<HardwareStatus | null>(null)

/** 状态徽章(CPU/内存/磁盘), hardware 为空时不渲染 */
const statusBadges = computed(() => {
  if (!hardware.value) return []
  const { cpu, memory, disk } = hardware.value
  return [
    { label: 'CPU', value: `${cpu.percent}%` },
    { label: '内存', value: `${memory.percent}%` },
    { label: '磁盘', value: `${disk.percent}%` },
  ]
})

// ===== 功能模块卡(与侧边栏菜单同源, 未登录仅显示无权限要求的分组) =====
interface ModuleCard {
  index: string
  target: string
  title: string
  desc: string
  icon?: Component
}

const moduleCards = computed<ModuleCard[]>(() => {
  return visibleMenuItems.value
    .filter((item) => item.index !== '/')
    .map((item) => ({
      index: item.index,
      // 有子菜单的分组跳转其第一个子页, 无子菜单的直接跳转自身
      target: item.children?.length ? item.children[0].index : item.index,
      title: item.title,
      desc: item.desc ?? '进入模块开始使用。',
      icon: item.icon,
    }))
})

onMounted(async () => {
  // 状态徽章容错: 接口失败/未登录 401 时保持 null, 徽章区隐藏
  if (!isLoggedIn.value) return
  try {
    // http 客户端直接返回业务数据(StatusServer)
    const res = await getStatusCache()
    hardware.value = res?.hardware ?? null
  } catch {
    hardware.value = null
  }
})
</script>
