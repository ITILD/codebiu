<template>
  <div class="p-4 md:p-6 w-full">
    <!-- 模块内页导航(应用页无侧边栏, 孙页面切换在此) -->
    <SitePageNav class="mb-4" />

    <!-- 顶部概览条: 三业务线速览(点击切换面板) -->
    <div class="mb-4 grid grid-cols-3 gap-2 md:gap-4">
      <button
        v-for="chip in overviewChips"
        :key="chip.key"
        type="button"
        class="rounded-xl border border-note bg-note-card p-3 text-left shadow-note transition-all hover:-translate-y-0.5 hover:shadow-md md:p-4"
        @click="active = chip.key"
      >
        <div class="flex items-center gap-1.5 text-xs text-note-sub">
          <el-icon><component :is="chip.icon" /></el-icon>
          {{ chip.label }}
        </div>
        <div class="mt-1 truncate text-base font-bold text-note md:text-xl">{{ chip.value }}</div>
      </button>
    </div>

    <!-- 待办提醒横幅(仅当今日有待办时渲染) -->
    <div
      v-if="todayTodos.length > 0"
      class="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-note bg-green-600/5 px-3 py-2"
    >
      <i class="i-ep-bell text-green-700 dark:text-green-400" />
      <span class="text-sm text-note">
        今日 <b>{{ todayTodos.length }}</b> 件待办：{{ todayTitles }}
      </span>
      <el-button size="small" text type="primary" class="ml-auto" @click="active = 'memo'">
        去处理 →
      </el-button>
    </div>

    <!-- 工作台: 左侧导航 + 右侧面板(移动端横向滚动) -->
    <div class="flex flex-col md:flex-row gap-4">
      <nav
        class="flex md:flex-col gap-1 md:w-44 shrink-0 bg-note-card rounded-lg shadow-note p-2 overflow-x-auto md:overflow-visible"
      >
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="flex items-center gap-2 rounded px-3 py-2 text-sm whitespace-nowrap transition-colors cursor-pointer"
          :class="active === tab.key
            ? 'bg-green-600/10 text-green-700 dark:text-green-400 font-medium'
            : 'text-note-sub hover:bg-note-glass'"
          @click="active = tab.key"
        >
          <el-icon><component :is="tab.icon" /></el-icon>
          {{ tab.label }}
        </button>
      </nav>

      <!-- 面板区: 首次激活才挂载(避免无权限/未使用面板的无效请求) -->
      <section class="flex-1 min-w-0">
        <Transition name="fade" mode="out-in">
          <BlogPanel v-if="active === 'blog'" key="blog" />
          <MemoPanel v-else-if="active === 'memo'" key="memo" />
          <LedgerPanel v-else-if="active === 'ledger'" key="ledger" />
        </Transition>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { markRaw } from 'vue'
import dayjs from 'dayjs'
import { EditPen, Bell, Wallet } from '@element-plus/icons-vue'
import SitePageNav from '../components/SitePageNav.vue'
import BlogPanel from '../components/panels/BlogPanel.vue'
import MemoPanel from '../components/panels/MemoPanel.vue'
import LedgerPanel from '../components/panels/LedgerPanel.vue'
import { listMyPosts } from '../api/blog'
import { listMemosByRange } from '../api/todolist'
import { getLedgerStats } from '../api/ledger'
import { localIsoStartOfDay, localIsoEndOfDay } from '../composables/useCalendar'
import type { Todolist } from '../types/todolist'

/**
 * 个人小站工作台: 博客/备忘/记账 三条业务线一页管理
 * 概览条与提醒横幅数据静默降级(部分业务线无权限时显示 '-')
 */

/** 面板分组(tab 同步到 ?tab= 查询参数, 刷新/分享保持) */
const tabs = [
  { key: 'blog', label: '博客管理', icon: markRaw(EditPen) },
  { key: 'memo', label: '备忘', icon: markRaw(Bell) },
  { key: 'ledger', label: '记账本', icon: markRaw(Wallet) },
] as const

type TabKey = (typeof tabs)[number]['key']

const route = useRoute()
const router = useRouter()
const validTabs = tabs.map((t) => t.key) as string[]
const active = ref<TabKey>(
  validTabs.includes(route.query.tab as string) ? (route.query.tab as TabKey) : 'blog',
)

// tab 切换同步 URL 查询参数
watch(active, (tab) => {
  router.replace({ query: { ...route.query, tab } })
  // 切换时刷新概览, 反映其他面板产生的数据变化
  loadOverview()
})

// ---------- 概览条 + 今日待办 ----------
const postCount = ref<number | null>(null)
const todoCount = ref<number | null>(null)
const monthExpense = ref<number | null>(null)
const todayTodos = ref<Todolist[]>([])

const overviewChips = computed(() => [
  { key: 'blog' as TabKey, icon: markRaw(EditPen), label: '我的文章', value: postCount.value === null ? '-' : `${postCount.value} 篇` },
  { key: 'memo' as TabKey, icon: markRaw(Bell), label: '今日待办', value: todoCount.value === null ? '-' : `${todoCount.value} 件` },
  { key: 'ledger' as TabKey, icon: markRaw(Wallet), label: '本月支出', value: monthExpense.value === null ? '-' : `¥${monthExpense.value.toFixed(2)}` },
])

const todayTitles = computed(() =>
  todayTodos.value.slice(0, 3).map((t) => t.name).join('、') +
  (todayTodos.value.length > 3 ? ' 等' : ''),
)

/** 拉取概览数据(各业务线独立静默降级, 无权限不互相影响) */
async function loadOverview() {
  // 文章数
  listMyPosts({ page: 1, size: 1 })
    .then((resp) => { postCount.value = resp.total })
    .catch(() => { postCount.value = null })
  // 今日待办(今日 0 点 ~ 明日 0 点, 过滤未完成)
  listMemosByRange(localIsoStartOfDay(new Date()), localIsoEndOfDay(new Date()))
    .then((items) => {
      todayTodos.value = items.filter((t) => t.status === 'todo')
      todoCount.value = todayTodos.value.length
    })
    .catch(() => {
      todayTodos.value = []
      todoCount.value = null
    })
  // 本月支出
  getLedgerStats(dayjs().format('YYYY-MM'))
    .then((stats) => { monthExpense.value = stats.expense_total })
    .catch(() => { monthExpense.value = null })
}

onMounted(loadOverview)
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
