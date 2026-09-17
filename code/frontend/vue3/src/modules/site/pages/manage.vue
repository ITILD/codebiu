<template>
  <div class="p-4 md:p-6 w-full">
    <!-- 顶部: 三业务线速览卡兼面板切换(激活态高亮, 替代原左侧导航) + 返回博客 -->
    <div class="mb-4 flex items-center gap-2 md:gap-4">
      <div class="grid flex-1 grid-cols-3 gap-2 md:gap-4">
        <button
          v-for="chip in overviewChips"
          :key="chip.key"
          type="button"
          class="note-glow-hover rounded-xl p-3 text-left shadow-note transition-all duration-200 hover:-translate-y-0.5 md:p-4"
          :class="active === chip.key ? 'bg-note-green/10' : 'bg-note-card'"
          @click="active = chip.key"
        >
          <div
            class="flex items-center gap-1.5 text-xs transition-colors"
            :class="active === chip.key ? 'font-medium text-note-green' : 'text-note-sub'"
          >
            <el-icon><component :is="chip.icon" /></el-icon>
            {{ chip.label }}
          </div>
          <!-- 数据未到: 与数值等高骨架条, 避免 '-'→数字 的抖动 -->
          <div
            class="mt-1 truncate text-base font-bold transition-colors md:text-xl"
            :class="active === chip.key ? 'text-note-green' : 'text-note'"
          >
            <span v-if="!overviewLoaded" class="note-sk inline-block h-5 w-12 align-middle md:h-6 md:w-14" />
            <template v-else>{{ chip.value }}</template>
          </div>
        </button>
      </div>
      <!-- 返回博客: 仅图标, 与概览条同行(同 index 页设置图标样式) -->
      <RouterLink
        to="/site"
        class="note-glow-hover flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-note-card text-sm text-note-sub shadow-note transition-colors hover:text-note-green"
        title="返回博客"
      >
        <i class="i-ep-back" />
      </RouterLink>
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

    <!-- 面板区: 首次激活才挂载(避免无权限/未使用面板的无效请求) -->
    <section>
      <Transition name="fade" mode="out-in">
        <BlogPanel v-if="active === 'blog'" key="blog" />
        <MemoPanel v-else-if="active === 'memo'" key="memo" />
        <LedgerPanel v-else-if="active === 'ledger'" key="ledger" />
      </Transition>
    </section>
  </div>
</template>

<script setup lang="ts">
import { markRaw } from 'vue'
import dayjs from 'dayjs'
import { EditPen, Bell, Wallet } from '@element-plus/icons-vue'
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

/** 面板 key(概览卡即切换器, tab 同步到 ?tab= 查询参数, 刷新/分享保持) */
type TabKey = 'blog' | 'memo' | 'ledger'

const validTabs: TabKey[] = ['blog', 'memo', 'ledger']

const route = useRoute()
const router = useRouter()
const active = ref<TabKey>(
  validTabs.includes(route.query.tab as TabKey) ? (route.query.tab as TabKey) : 'blog',
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
/** 首轮概览是否全部落地(失败也算落地, 展示 '-' 而非永久骨架) */
const overviewLoaded = ref(false)

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
  const p1 = listMyPosts({ page: 1, size: 1 })
    .then((resp) => { postCount.value = resp.total })
    .catch(() => { postCount.value = null })
  // 今日待办(今日 0 点 ~ 明日 0 点, 过滤未完成)
  const p2 = listMemosByRange(localIsoStartOfDay(new Date()), localIsoEndOfDay(new Date()))
    .then((items) => {
      todayTodos.value = items.filter((t) => t.status === 'todo')
      todoCount.value = todayTodos.value.length
    })
    .catch(() => {
      todayTodos.value = []
      todoCount.value = null
    })
  // 本月支出
  const p3 = getLedgerStats(dayjs().format('YYYY-MM'))
    .then((stats) => { monthExpense.value = stats.expense_total })
    .catch(() => { monthExpense.value = null })
  // 首轮全部结束(无论成败)即收骨架; 后续 tab 刷新不再显示骨架
  await Promise.allSettled([p1, p2, p3])
  overviewLoaded.value = true
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
