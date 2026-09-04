<template>
  <div p-4 md:p-6>
    <!-- 欢迎区: 时段问候 + 刷新 -->
    <div mb-6 flex items-center justify-between flex-wrap gap-4>
      <div>
        <h2 text-2xl font-bold text-note>{{ greeting }}，{{ displayName }}</h2>
        <p text-sm text-note-sub mt-1>欢迎使用后台管理工作台，祝您高效顺利。</p>
      </div>
      <el-button :icon="Refresh" bg-note-green text-white @click="loadStatus">刷新数据</el-button>
    </div>

    <!-- 服务器状态统计卡(真实数据: getStatusCache 60s 缓存接口) -->
    <div grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6>
      <div
        v-for="card in statCards"
        :key="card.label"
        bg-note-card border border-note rounded-xl p-5 shadow-note
      >
        <div flex items-center justify-between>
          <div min-w-0>
            <p text-sm text-note-sub>{{ card.label }}</p>
            <p text-2xl font-bold mt-2 text-note-green>{{ card.value }}</p>
            <p text-xs text-note-sub mt-1 truncate>{{ card.sub }}</p>
          </div>
          <div w-11 h-11 rounded-full bg-note-tint center shrink-0>
            <el-icon :size="24" text-note-green><component :is="card.icon" /></el-icon>
          </div>
        </div>
      </div>
    </div>

    <!-- 快捷入口 -->
    <div mb-6>
      <h3 text-lg font-semibold text-note mb-4>快捷入口</h3>
      <div grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3>
        <RouterLink
          v-for="shortcut in shortcuts"
          :key="shortcut.path"
          :to="shortcut.path"
          flex flex-col items-center p-4 rounded-xl bg-note-tint border border-note
          transition-all duration-300 hover:-translate-y-1 hover:shadow-note hover:bg-note-card
        >
          <el-icon :size="28" mb-2 text-note-green>
            <component :is="shortcut.icon" />
          </el-icon>
          <span text-sm text-note>{{ shortcut.title }}</span>
        </RouterLink>
      </div>
    </div>

    <div grid grid-cols-1 lg:grid-cols-2 gap-4>
      <!-- 最近访问(localStorage 采集, 与主页共用) -->
      <div bg-note-card border border-note rounded-xl p-5>
        <h3 font-semibold text-note mb-3>最近访问</h3>
        <template v-if="recentPages.length">
          <div
            v-for="item in recentPages"
            :key="item.path"
            flex items-center justify-between p-2 rounded-lg hover:bg-note-tint cursor-pointer transition-colors
            @click="router.push(item.path)"
          >
            <div flex items-center gap-2 min-w-0>
              <el-icon text-note-sub><Clock /></el-icon>
              <span text-sm text-note truncate>{{ item.title }}</span>
            </div>
            <el-icon text-note-sub><ArrowRight /></el-icon>
          </div>
        </template>
        <p v-else text-sm text-note-sub>暂无访问记录，左侧菜单开始探索吧。</p>
      </div>

      <!-- 系统信息 -->
      <div bg-note-card border border-note rounded-xl p-5>
        <h3 font-semibold text-note mb-3>系统信息</h3>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="系统版本">v1.0.0</el-descriptions-item>
          <el-descriptions-item label="运行环境">{{ envText }}</el-descriptions-item>
          <el-descriptions-item label="主题模式">{{ sysSettingStore.sysStyle.theme.isDark ? '深色' : '浅色' }}</el-descriptions-item>
          <el-descriptions-item label="屏幕档位">{{ screenLabel }}</el-descriptions-item>
        </el-descriptions>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { markRaw, ref, computed, onMounted, onUnmounted } from 'vue'
import {
  Refresh, Cpu, Coin, Filter, Connection, Clock, ArrowRight,
} from '@element-plus/icons-vue'
import type { Component } from 'vue'
import { useRouter } from 'vue-router'
import { SysSettingStore } from '@/common/stores/sys'
import { useAuthStore } from '@/common/stores/auth'
import { useVisibleMenu } from '@/common/composables/useMenu'
import { useRecentPages } from '@/common/composables/useRecentPages'
import { getStatusCache } from '@/modules/main/api/status'
import type { HardwareStatus, NetworkStatus } from '@/modules/main/types/status'

const router = useRouter()
const sysSettingStore = SysSettingStore()
const authStore = useAuthStore()
const { recentPages } = useRecentPages()
const { visibleMenuItems } = useVisibleMenu()

const displayName = computed(() => authStore.authState.user.nickname || authStore.authState.user.username || '管理员')

/** 按时段返回问候语 */
function greetingByHour(): string {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
}
const greeting = ref(greetingByHour())

const envText = import.meta.env.MODE === 'development' ? '开发环境' : '生产环境'

/** 屏幕档位描述(三档断点) */
const screenLabel = computed(() => {
  const s = sysSettingStore.sysStyle
  if (s.isLg) return '桌面(≥1024)'
  if (s.isMd) return '平板(768-1023)'
  return '手机(<768)'
})

// ===== 服务器状态(真实数据) =====
const hardware = ref<HardwareStatus | null>(null)
const network = ref<NetworkStatus[] | null>(null)

/** 统计卡: hardware 为 null 时显示 '-' */
const statCards = computed<{ label: string; value: string; sub: string; icon: Component }[]>(() => {
  const hw = hardware.value
  return [
    {
      label: 'CPU 使用率',
      value: hw ? `${hw.cpu.percent}%` : '-',
      sub: hw ? `${hw.cpu.cores} 核 / ${hw.cpu.threads} 线程` : '暂无数据',
      icon: markRaw(Cpu),
    },
    {
      label: '内存使用率',
      value: hw ? `${hw.memory.percent}%` : '-',
      sub: hw ? `${hw.memory.used} / ${hw.memory.total} GB` : '暂无数据',
      icon: markRaw(Coin),
    },
    {
      label: '磁盘使用率',
      value: hw ? `${hw.disk.percent}%` : '-',
      sub: hw ? `${hw.disk.used} / ${hw.disk.total} GB` : '暂无数据',
      icon: markRaw(Filter),
    },
    {
      label: '网络连通',
      value: network.value
        ? `${network.value.filter((n) => n.connect_success).length}/${network.value.length}`
        : '-',
      sub: '外网探测成功数 / 总数',
      icon: markRaw(Connection),
    },
  ]
})

/** 拉取服务器状态(60s 缓存接口, 失败静默保持 '-') */
async function loadStatus() {
  try {
    const res = await getStatusCache()
    hardware.value = res?.hardware ?? null
    network.value = res?.network ?? null
  } catch {
    // 静默降级: 卡片显示 '-'
  }
}

// ===== 快捷入口: 从菜单树按路径挑选(自动带权限过滤, 未授权自动隐藏), 图标取父分组 =====
const SHORTCUT_PATHS = [
  '/authorization/user',
  '/rag/project',
  '/ai/chat',
  '/file',
  '/little_utils/todolist',
  '/monitor/server_status',
] as const

const shortcuts = computed(() => {
  // 展平菜单树并携带所属分组图标(显式标注避免分支类型不兼容)
  type FlatItem = { index: string; title: string; icon?: Component }
  const flatten: FlatItem[] = visibleMenuItems.value.flatMap((g): FlatItem[] =>
    g.children?.length
      ? g.children.map((c) => ({ index: c.index, title: c.title, icon: g.icon }))
      : [{ index: g.index, title: g.title, icon: g.icon }]
  )
  return SHORTCUT_PATHS.map((path) => flatten.find((m) => m.index === path))
    .filter((m): m is FlatItem => Boolean(m))
    .map((m) => ({ path: m.index, title: m.title, icon: m.icon }))
})

// 60s 自动刷新(与后端缓存周期对齐), 离开页面清理
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  loadStatus()
  timer = setInterval(loadStatus, 60_000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>
