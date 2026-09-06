<template>
  <div class="w-full">
    <!-- 月份导航 + 记一笔入口 -->
    <div class="mb-4 flex flex-wrap items-center gap-1.5">
      <el-button :icon="ArrowLeft" text @click="stepMonth(-1)" />
      <el-date-picker
        v-model="monthValue"
        type="month"
        format="YYYY年MM月"
        value-format="YYYY-MM"
        :clearable="false"
        class="w-[130px]!"
      />
      <el-button :icon="ArrowRight" text @click="stepMonth(1)" />
      <el-button size="small" text type="primary" @click="goThisMonth">本月</el-button>
      <el-button type="primary" :icon="Plus" class="ml-auto" @click="openCreate">记一笔</el-button>
    </div>

    <!-- 月度概览: 收入/支出/结余 -->
    <div class="mb-4 grid grid-cols-3 gap-2 md:gap-4">
      <div class="rounded-xl border border-note bg-note-card p-3 shadow-note md:p-4">
        <div class="text-xs text-note-sub">本月收入</div>
        <div class="mt-1 truncate text-base font-bold text-note md:text-2xl">
          ¥ {{ fmtMoney(stats?.income_total ?? 0) }}
        </div>
      </div>
      <div class="rounded-xl border border-note bg-note-card p-3 shadow-note md:p-4">
        <div class="text-xs text-note-sub">本月支出</div>
        <div class="mt-1 truncate text-base font-bold text-note md:text-2xl">
          ¥ {{ fmtMoney(stats?.expense_total ?? 0) }}
        </div>
      </div>
      <div class="rounded-xl border border-note bg-note-card p-3 shadow-note md:p-4">
        <div class="text-xs text-note-sub">本月结余</div>
        <div
          class="mt-1 truncate text-base font-bold md:text-2xl"
          :class="(stats?.balance ?? 0) >= 0 ? 'text-green-600' : 'text-red-500'"
        >
          ¥ {{ fmtMoney(stats?.balance ?? 0) }}
        </div>
      </div>
    </div>

    <!-- 图表区: 支出分类饼图 + 近6月收支趋势(移动端堆叠) -->
    <div class="mb-4 grid grid-cols-1 gap-2 md:gap-4 lg:grid-cols-2">
      <div class="rounded-xl border border-note bg-note-card p-3 shadow-note">
        <div class="mb-1 text-sm font-bold text-note">支出分类占比</div>
        <div ref="pieEl" class="h-[240px] w-full md:h-[280px]" />
      </div>
      <div class="rounded-xl border border-note bg-note-card p-3 shadow-note">
        <div class="mb-1 text-sm font-bold text-note">近6月收支趋势</div>
        <div ref="barEl" class="h-[240px] w-full md:h-[280px]" />
      </div>
    </div>

    <!-- 明细过滤: 分类/方向 -->
    <TableSearchBar
      v-model="queryParams"
      :fields="searchFields"
      @search="handleSearch"
      @reset="handleSearch"
    />

    <!-- 记账明细表 -->
    <el-table :data="tableData" v-loading="loading" stripe w-full>
      <el-table-column label="日期" min-width="110">
        <template #default="{ row }">{{ row.occurred_at }}</template>
      </el-table-column>
      <el-table-column label="方向" min-width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.flow_type === 'income' ? 'success' : 'danger'" size="small" effect="plain">
            {{ row.flow_type === 'income' ? '收入' : '支出' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="category" label="分类" min-width="100" show-overflow-tooltip />
      <el-table-column label="金额" min-width="120" align="right">
        <template #default="{ row }">
          <span :class="row.flow_type === 'income' ? 'text-green-600' : 'text-red-500'" class="font-bold">
            {{ row.flow_type === 'income' ? '+' : '-' }}{{ fmtMoney(row.amount) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="备注" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ row.note || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" min-width="150" :fixed="isMd ? 'right' : false">
        <template #default="{ row }">
          <el-button size="small" plain @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" plain @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页(手机居中, 桌面靠右) -->
    <div class="mt-4 flex flex-wrap justify-center sm:justify-end">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.size"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="fetchData"
      />
    </div>

    <!-- 记一笔/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="currentId ? '编辑记录' : '记一笔'"
      width="90%"
      class="max-w-[480px]!"
    >
      <el-form :model="form" label-width="70px">
        <el-form-item label="方向">
          <el-radio-group v-model="form.flow_type">
            <el-radio-button value="expense">支出</el-radio-button>
            <el-radio-button value="income">收入</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="金额" required>
          <el-input-number
            v-model="form.amount"
            :min="0.01"
            :max="9999999"
            :precision="2"
            :step="10"
            class="w-full!"
            placeholder="0.00"
          />
        </el-form-item>
        <el-form-item label="分类" required>
          <el-select
            v-model="form.category"
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入分类"
            class="w-full!"
          >
            <el-option v-for="cat in categoryOptions" :key="cat" :label="cat" :value="cat" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker
            v-model="form.occurred_at"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择记账日期"
            class="w-full!"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.note" placeholder="备注(可选)" maxlength="200" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ArrowLeft, ArrowRight, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import {
  createLedgerRecord,
  deleteLedgerRecord,
  getLedgerStats,
  listLedgerRecords,
  updateLedgerRecord,
} from '../../api/ledger'
import { useChart } from '../../composables/useChart'
import type { LedgerFlow, LedgerRecord, LedgerStats } from '../../types/ledger'
import type { SearchField } from '@/common/components/TableSearchBar.vue'
import { useResponsive } from '@/common/composables/useResponsive'

// 响应式断点(md 以下操作列不固定, 靠横向滚动)
const { isMd } = useResponsive()

// ---------- 月份导航 ----------
const monthValue = ref(dayjs().format('YYYY-MM'))
const stepMonth = (delta: number) => {
  monthValue.value = dayjs(monthValue.value).add(delta, 'month').format('YYYY-MM')
}
const goThisMonth = () => {
  monthValue.value = dayjs().format('YYYY-MM')
}
// 月份切换: 统计与明细一起刷新
watch(monthValue, () => {
  pagination.value.page = 1
  fetchStats()
  fetchData()
})

// ---------- 月度统计 + 图表 ----------
const stats = ref<LedgerStats | null>(null)
const pieEl = ref<HTMLElement | null>(null)
const barEl = ref<HTMLElement | null>(null)
const { render: renderPie } = useChart(pieEl)
const { render: renderBar } = useChart(barEl)

/** 淡雅自然风图表配色 */
const PALETTE = ['#7fb069', '#a3c9a8', '#e8985e', '#6a9fb5', '#c9a7a7', '#b5a76a', '#9b8bb4', '#8fb8c9']

async function fetchStats() {
  try {
    stats.value = await getLedgerStats(monthValue.value)
  } catch (error) {
    console.error('获取记账统计失败:', error)
    stats.value = null
    return
  }
  renderPieChart()
  renderBarChart()
}

/** 支出分类饼图(环形, 空数据时居中提示) */
function renderPieChart() {
  const pie = stats.value?.category_pie ?? []
  renderPie({
    color: PALETTE,
    tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
    legend: { bottom: 0, type: 'scroll', icon: 'circle', itemWidth: 8, itemHeight: 8, textStyle: { fontSize: 12 } },
    title: pie.length
      ? undefined
      : { text: '本月暂无支出', left: 'center', top: 'middle', textStyle: { color: '#999', fontSize: 13, fontWeight: 'normal' } },
    series: [{
      type: 'pie',
      radius: ['42%', '68%'],
      center: ['50%', '44%'],
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      data: pie.map((x) => ({ name: x.category, value: x.total })),
    }],
  })
}

/** 近6月收支趋势(双柱) */
function renderBarChart() {
  const trend = stats.value?.trend ?? []
  renderBar({
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, itemWidth: 12, itemHeight: 8, textStyle: { fontSize: 12 } },
    grid: { left: 8, right: 8, top: 20, bottom: 32, containLabel: true },
    xAxis: { type: 'category', data: trend.map((t) => t.month.slice(5) + '月') },
    yAxis: { type: 'value' },
    series: [
      {
        name: '收入',
        type: 'bar',
        barMaxWidth: 22,
        itemStyle: { borderRadius: [4, 4, 0, 0], color: '#7fb069' },
        data: trend.map((t) => t.income),
      },
      {
        name: '支出',
        type: 'bar',
        barMaxWidth: 22,
        itemStyle: { borderRadius: [4, 4, 0, 0], color: '#e8985e' },
        data: trend.map((t) => t.expense),
      },
    ],
  })
}

// ---------- 明细列表 ----------
/** 明细过滤字段(分类模糊 + 方向) */
const searchFields: SearchField[] = [
  { prop: 'category', label: '分类' },
  {
    prop: 'flow_type', label: '方向', type: 'select', options: [
      { label: '支出', value: 'expense' },
      { label: '收入', value: 'income' },
    ],
  },
]
const queryParams = ref<Record<string, unknown>>({ category: '', flow_type: undefined })
const pagination = ref({ page: 1, size: 10 })
const tableData = ref<LedgerRecord[]>([])
const total = ref(0)
const loading = ref(false)

async function fetchData() {
  loading.value = true
  try {
    const { category, flow_type } = queryParams.value
    const resp = await listLedgerRecords({
      ...pagination.value,
      month: monthValue.value,
      category: (category as string) || undefined,
      flow_type: (flow_type as string) || undefined,
    })
    tableData.value = resp.items
    total.value = resp.total
    // 当前页无数据且非第一页时回退一页
    if (resp.items.length === 0 && pagination.value.page > 1) {
      pagination.value.page -= 1
      await fetchData()
    }
  } catch (error) {
    console.error('获取记账明细失败:', error)
    ElMessage.error('获取记账明细失败，请重试')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.value.page = 1
  fetchData()
}

// ---------- 记一笔/编辑 ----------
/** 常用分类预设(随方向切换) */
const EXPENSE_CATEGORIES = ['餐饮', '交通', '购物', '居住', '娱乐', '医疗', '学习', '其他']
const INCOME_CATEGORIES = ['工资', '理财', '兼职', '红包', '其他']
const categoryOptions = computed(() =>
  form.flow_type === 'income' ? INCOME_CATEGORIES : EXPENSE_CATEGORIES,
)

const dialogVisible = ref(false)
const currentId = ref<string | null>(null)
const submitting = ref(false)
const form = reactive({
  flow_type: 'expense' as LedgerFlow,
  amount: undefined as number | undefined,
  category: '',
  occurred_at: dayjs().format('YYYY-MM-DD'),
  note: '',
})

function resetForm() {
  currentId.value = null
  form.flow_type = 'expense'
  form.amount = undefined
  form.category = ''
  form.occurred_at = dayjs().format('YYYY-MM-DD')
  form.note = ''
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: LedgerRecord) {
  resetForm()
  currentId.value = row.id
  form.flow_type = row.flow_type
  form.amount = row.amount
  form.category = row.category
  form.occurred_at = row.occurred_at
  form.note = row.note ?? ''
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!form.amount || form.amount <= 0) {
    ElMessage.warning('请输入有效金额')
    return
  }
  if (!form.category.trim()) {
    ElMessage.warning('请选择或输入分类')
    return
  }
  submitting.value = true
  try {
    const payload = {
      amount: form.amount,
      flow_type: form.flow_type,
      category: form.category.trim(),
      occurred_at: form.occurred_at,
      note: form.note.trim() || null,
    }
    if (currentId.value) {
      await updateLedgerRecord(currentId.value, payload)
      ElMessage.success('记录已更新')
    } else {
      await createLedgerRecord(payload)
      ElMessage.success('已记一笔')
    }
    dialogVisible.value = false
    // 记账日期可能不在当前查看月份, 统计与明细都刷新
    fetchStats()
    handleSearch()
  } catch (error) {
    console.error('保存记账失败:', error)
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: LedgerRecord) {
  try {
    await ElMessageBox.confirm(
      `确定删除 ${row.occurred_at} 的「${row.category}」记录吗？`,
      '警告',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' },
    )
    await deleteLedgerRecord(row.id)
    ElMessage.success('删除成功')
    if (tableData.value.length === 1 && pagination.value.page > 1) pagination.value.page -= 1
    fetchStats()
    fetchData()
  } catch {
    // 用户取消
  }
}

/** 金额千分位 + 两位小数 */
const fmtMoney = (n: number) =>
  n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

onMounted(() => {
  fetchStats()
  fetchData()
})
</script>
