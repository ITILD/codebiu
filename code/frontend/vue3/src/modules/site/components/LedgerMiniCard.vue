<template>
  <!-- 记账分析迷你卡: 月/年快捷切换 + 本期结余概览 + 支出分类 top3 + 迷你支出趋势条 -->
  <div
    v-if="stats"
    class="w-full rounded-xl border border-note bg-note-card p-3 text-left shadow-note"
  >
    <!-- 标题 + 月/年切换 -->
    <div class="flex items-center justify-between gap-2">
      <span class="text-xs font-bold text-note">记账分析</span>
      <el-radio-group v-model="mode" size="small" @change="onModeChange">
        <el-radio-button value="month">月</el-radio-button>
        <el-radio-button value="year">年</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 周期导航: 上一期 / 回本期 / 下一期 -->
    <div class="mt-1 flex items-center justify-between">
      <el-button size="small" text :icon="ArrowLeft" @click="step(-1)" />
      <button
        type="button"
        class="text-xs font-bold text-note hover:opacity-80"
        :title="`回到${mode === 'month' ? '本月' : '今年'}`"
        @click="goCurrent"
      >{{ periodLabel }}</button>
      <el-button size="small" text :icon="ArrowRight" @click="step(1)" />
    </div>

    <!-- 结余大数字 -->
    <div
      class="mt-1 truncate text-xl font-bold"
      :class="stats.balance >= 0 ? 'text-green-600' : 'text-red-500'"
    >
      ¥ {{ fmtMoney(stats.balance) }}
    </div>

    <!-- 收入/支出两行 -->
    <div class="mt-2 flex items-center justify-between text-xs text-note-sub">
      <span>收入 <b class="text-green-600">+{{ fmtMoney(stats.income_total) }}</b></span>
      <span>支出 <b class="text-red-500">-{{ fmtMoney(stats.expense_total) }}</b></span>
    </div>

    <!-- 支出分类 top3 迷你进度条 -->
    <div v-if="topCategories.length > 0" class="mt-2.5 space-y-1.5">
      <div v-for="item in topCategories" :key="item.category">
        <div class="flex items-center justify-between text-xs text-note-sub">
          <span>{{ item.category }}</span>
          <span>¥{{ fmtMoney(item.total) }}</span>
        </div>
        <div class="mt-0.5 h-1.5 w-full overflow-hidden rounded-full bg-note-soft">
          <div
            class="h-full rounded-full bg-green-600/60"
            :style="{ width: `${(item.total / maxCategoryTotal) * 100}%` }"
          />
        </div>
      </div>
    </div>
    <div v-else class="mt-2 text-xs text-note-sub">{{ mode === 'month' ? '本月' : '本年' }}暂无支出记录</div>

    <!-- 迷你支出趋势条(月模式近6月 / 年模式12个月, 点击切换到对应月份) -->
    <div v-if="maxTrendExpense > 0" class="mt-2.5">
      <div class="mb-1 flex items-center justify-between text-[10px] text-note-sub">
        <span>支出趋势</span>
        <span>{{ mode === 'month' ? '近6月' : '全年12月' }}</span>
      </div>
      <div class="flex h-10 items-end gap-[3px]">
        <button
          v-for="t in stats.trend"
          :key="t.month"
          type="button"
          class="flex h-full min-w-0 flex-1 cursor-pointer flex-col justify-end rounded-sm transition-opacity hover:opacity-70"
          :title="`${t.month} 支出 ¥${fmtMoney(t.expense)}`"
          @click="jumpMonth(t.month)"
        >
          <div
            class="w-full rounded-sm"
            :style="{ height: `${Math.max((t.expense / maxTrendExpense) * 100, 4)}%`, backgroundColor: 'rgba(232, 152, 94, 0.7)' }"
          />
        </button>
      </div>
    </div>

    <div class="mt-2 text-right">
      <el-button size="small" text type="primary" @click="router.push('/site?tab=ledger')">
        查看记账本 →
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
// 无数据(接口失败/无权限)时整卡隐藏
import dayjs from 'dayjs'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { getLedgerStats } from '../api/ledger'
import type { LedgerStats } from '../types/ledger'

const router = useRouter()
const stats = ref<LedgerStats | null>(null)

// ---------- 周期切换(月/年) ----------
/** 统计模式: 月度(YYYY-MM) / 年度(YYYY) */
const mode = ref<'month' | 'year'>('month')
/** 当前统计周期: 月模式 YYYY-MM, 年模式 YYYY */
const period = ref(dayjs().format('YYYY-MM'))

/** 用户切换模式 → 快捷回到本期(本月/今年)并重新拉取 */
function onModeChange() {
  period.value = mode.value === 'month' ? dayjs().format('YYYY-MM') : dayjs().format('YYYY')
}

/** 上/下一周期(月±1 / 年±1) */
function step(dir: 1 | -1) {
  period.value = mode.value === 'month'
    ? dayjs(`${period.value}-01`).add(dir, 'month').format('YYYY-MM')
    : String(Number(period.value) + dir)
}

/** 回到本期(本月/今年) */
function goCurrent() {
  period.value = mode.value === 'month' ? dayjs().format('YYYY-MM') : dayjs().format('YYYY')
}

/** 周期标题 */
const periodLabel = computed(() => {
  if (mode.value === 'year') return `${period.value}年`
  const [y, m] = period.value.split('-')
  return `${y}年${Number(m)}月`
})

// 周期变化 → 重新拉取统计
watch(period, fetchStats, { immediate: true })

async function fetchStats() {
  try {
    stats.value = await getLedgerStats(period.value)
  } catch {
    // 静默隐藏整卡(无权限/网络失败)
    stats.value = null
  }
}

/** 点击趋势条跳到对应月份(年模式 → 月模式查看单月) */
function jumpMonth(month: string) {
  mode.value = 'month'
  period.value = month
}

// ---------- 派生数据 ----------
/** 支出分类 top3 */
const topCategories = computed(() =>
  (stats.value?.category_pie ?? []).slice(0, 3),
)
const maxCategoryTotal = computed(() =>
  topCategories.value[0]?.total ?? 1,
)

/** 趋势条最大支出(用于归一化高度) */
const maxTrendExpense = computed(() =>
  Math.max(0, ...(stats.value?.trend ?? []).map((t) => t.expense)),
)

const fmtMoney = (n: number) =>
  n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
</script>
