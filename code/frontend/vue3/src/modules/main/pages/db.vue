<template>
  <div p-4 md:p-6>
    <InkPageHead title="数据监测" sub="关系库 / 向量库 / 缓存 / 图数据库的数据量与运行情况" seal="测">
      <template #actions>
        <el-input
          v-if="activeTab === 'rel'"
          v-model="keyword"
          placeholder="按表名/注释搜索"
          clearable
          w-56
          @clear="fetchTables"
          @keyup.enter="fetchTables"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button :icon="Refresh" plain @click="fetchActive">刷新</el-button>
      </template>
    </InkPageHead>

    <el-tabs v-model="activeTab" @tab-change="handleTabChange">
      <!-- ==================== 关系数据库 ==================== -->
      <el-tab-pane label="关系数据库" name="rel">
        <!-- 概览统计 -->
        <div class="stat-row" mb-4>
          <div class="stat-card">
            <div class="stat-icon icon-blue">
              <el-icon :size="22"><Coin /></el-icon>
            </div>
            <div class="stat-meta">
              <div class="stat-value">{{ tableList.length }}</div>
              <div class="stat-label">数据表</div>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon icon-green">
              <el-icon :size="22"><Tickets /></el-icon>
            </div>
            <div class="stat-meta">
              <div class="stat-value">{{ totalRows.toLocaleString() }}</div>
              <div class="stat-label">总记录数</div>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon icon-orange">
              <el-icon :size="22"><Clock /></el-icon>
            </div>
            <div class="stat-meta">
              <div class="stat-value stat-time">{{ lastUpdatedOverall || '-' }}</div>
              <div class="stat-label">最近数据更新</div>
            </div>
          </div>
        </div>

        <!-- 图表区 -->
        <div class="chart-row" mb-4>
          <el-card shadow="never" class="chart-card">
            <template #header>
              <div class="card-head">数据条数 TOP 10</div>
            </template>
            <div ref="barRef" class="chart-box" />
          </el-card>
          <el-card shadow="never" class="chart-card">
            <template #header>
              <div class="card-head">数据量占比</div>
            </template>
            <div ref="pieRef" class="chart-box" />
          </el-card>
        </div>

        <!-- 数据表清单 -->
        <el-card shadow="never">
          <el-table
            :data="tableList"
            v-loading="relLoading"
            stripe
            w-full
            :row-class-name="rowClassName"
          >
            <el-table-column type="index" label="#" width="60" />
            <el-table-column prop="name" label="表名" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                <span font-mono text-13px>{{ row.name }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="comment" label="注释" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.comment" text-muted>{{ row.comment }}</span>
                <span v-else text-subtle>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="column_count" label="字段数" width="90" align="center" />
            <el-table-column prop="row_count" label="数据条数" width="120" align="right" sortable>
              <template #default="{ row }">
                <span v-if="row.row_count > 0" font-mono>{{ row.row_count.toLocaleString() }}</span>
                <span v-else font-mono text-subtle>0</span>
              </template>
            </el-table-column>
            <el-table-column prop="last_updated" label="最后更新" width="170" sortable>
              <template #default="{ row }">
                <div v-if="row.last_updated" class="time-cell">
                  <span>{{ fmtTime(row.last_updated) }}</span>
                  <el-tag v-if="isToday(row.last_updated)" size="small" type="success" effect="plain">
                    今天
                  </el-tag>
                </div>
                <span v-else text-subtle>-</span>
              </template>
            </el-table-column>
          </el-table>

          <el-empty
            v-if="!relLoading && tableList.length === 0"
            :description="keyword ? '没有匹配的数据表' : '暂无数据表'"
            :image-size="72"
          />
        </el-card>
      </el-tab-pane>

      <!-- ==================== 向量数据库 ==================== -->
      <el-tab-pane label="向量数据库" name="vector">
        <template v-if="vectorInfo?.type">
          <!-- 概览统计 -->
          <div class="stat-row" mb-4>
            <div class="stat-card">
              <div class="stat-icon icon-blue">
                <el-icon :size="22"><Collection /></el-icon>
              </div>
              <div class="stat-meta">
                <div class="stat-value">{{ vectorTables.length }}</div>
                <div class="stat-label">向量表</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon icon-green">
                <el-icon :size="22"><Tickets /></el-icon>
              </div>
              <div class="stat-meta">
                <div class="stat-value">{{ totalVectors.toLocaleString() }}</div>
                <div class="stat-label">总数据量</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon icon-orange">
                <el-icon :size="22"><Cpu /></el-icon>
              </div>
              <div class="stat-meta">
                <div class="stat-value">{{ vectorInfo.type }}</div>
                <div class="stat-label">实现类型</div>
              </div>
            </div>
          </div>

          <el-card shadow="never">
            <el-table :data="vectorTables" v-loading="vectorLoading" stripe w-full>
              <el-table-column type="index" label="#" width="60" />
              <el-table-column prop="name" label="表名" min-width="220" show-overflow-tooltip>
                <template #default="{ row }">
                  <span font-mono text-13px>{{ row.name }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="field_count" label="字段数" width="100" align="center">
                <template #default="{ row }">
                  <span v-if="row.field_count != null" font-mono>{{ row.field_count }}</span>
                  <span v-else text-subtle>-</span>
                </template>
              </el-table-column>
              <el-table-column prop="vector_dims" label="向量维度" width="110" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.vector_dims" size="small" effect="plain" font-mono>
                    {{ row.vector_dims }}
                  </el-tag>
                  <span v-else text-subtle>-</span>
                </template>
              </el-table-column>
              <el-table-column prop="row_count" label="数据条数" width="140" align="right" sortable>
                <template #default="{ row }">
                  <span v-if="row.row_count != null" font-mono>{{ row.row_count.toLocaleString() }}</span>
                  <span v-else text-subtle>-</span>
                </template>
              </el-table-column>
            </el-table>

            <el-empty
              v-if="!vectorLoading && vectorTables.length === 0"
              description="暂无向量表"
              :image-size="72"
            />
          </el-card>
        </template>
        <el-card v-else shadow="never">
          <el-empty v-loading="vectorLoading" description="未启用向量数据库" :image-size="72" />
        </el-card>
      </el-tab-pane>

      <!-- ==================== Redis 缓存 ==================== -->
      <el-tab-pane label="Redis 缓存" name="cache">
        <template v-if="cacheInfo?.type">
          <!-- 概览统计 -->
          <div class="stat-row" mb-4>
            <div class="stat-card">
              <div class="stat-icon icon-blue">
                <el-icon :size="22"><Key /></el-icon>
              </div>
              <div class="stat-meta">
                <div class="stat-value">{{ (cacheInfo.dbsize ?? 0).toLocaleString() }}</div>
                <div class="stat-label">键数量</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon icon-green">
                <el-icon :size="22"><Coin /></el-icon>
              </div>
              <div class="stat-meta">
                <div class="stat-value">{{ cacheInfo.used_memory_human || '-' }}</div>
                <div class="stat-label">内存占用</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon icon-orange">
                <el-icon :size="22"><Odometer /></el-icon>
              </div>
              <div class="stat-meta">
                <div class="stat-value">
                  {{ cacheInfo.hit_rate != null ? `${cacheInfo.hit_rate}%` : '-' }}
                </div>
                <div class="stat-label">缓存命中率</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon icon-purple">
                <el-icon :size="22"><Timer /></el-icon>
              </div>
              <div class="stat-meta">
                <div class="stat-value">{{ cacheInfo.uptime_in_days ?? '-' }}</div>
                <div class="stat-label">运行天数</div>
              </div>
            </div>
          </div>

          <el-card shadow="never">
            <template #header>
              <div class="card-head">运行信息{{ cacheInfo.redis_version ? `（Redis ${cacheInfo.redis_version}）` : '' }}</div>
            </template>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="实现类型">{{ cacheInfo.type }}</el-descriptions-item>
              <el-descriptions-item label="键数量">{{ (cacheInfo.dbsize ?? 0).toLocaleString() }}</el-descriptions-item>
              <el-descriptions-item label="内存占用">{{ cacheInfo.used_memory_human || '-' }}</el-descriptions-item>
              <el-descriptions-item label="最大内存">{{ cacheInfo.maxmemory_human || '不限制' }}</el-descriptions-item>
              <el-descriptions-item label="连接客户端">{{ cacheInfo.connected_clients ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="运行天数">{{ cacheInfo.uptime_in_days ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="键空间命中">{{ (cacheInfo.keyspace_hits ?? 0).toLocaleString() }}</el-descriptions-item>
              <el-descriptions-item label="键空间未命中">{{ (cacheInfo.keyspace_misses ?? 0).toLocaleString() }}</el-descriptions-item>
            </el-descriptions>
          </el-card>
        </template>
        <el-card v-else shadow="never">
          <el-empty v-loading="cacheLoading" description="未启用缓存数据库" :image-size="72" />
        </el-card>
      </el-tab-pane>

      <!-- ==================== 图数据库 ==================== -->
      <el-tab-pane label="图数据库" name="graph">
        <el-card v-if="graphInfo?.type" shadow="never">
          <template #header>
            <div class="card-head">运行信息</div>
          </template>
          <el-descriptions :column="2" border>
            <el-descriptions-item v-for="[gkey, gvalue] in graphEntries" :key="gkey" :label="gkey">
              <template v-if="typeof gvalue === 'boolean'">
                <el-tag :type="gvalue ? 'success' : 'danger'" size="small" effect="plain">
                  {{ gvalue ? '已连接' : '未连接' }}
                </el-tag>
              </template>
              <span v-else font-mono text-13px>{{ gvalue }}</span>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
        <el-card v-else shadow="never">
          <el-empty v-loading="graphLoading" description="未启用图数据库" :image-size="72" />
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import {
  Search, Refresh, Coin, Tickets, Clock,
  Collection, Cpu, Key, Odometer, Timer,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
// echarts 按需引入
import * as echarts from 'echarts/core'
import { BarChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import {
  listDbTables,
  listVectorTables,
  getCacheInfo,
  getGraphInfo,
  type DbTableInfo,
  type DbVectorInfo,
  type DbCacheInfo,
  type DbGraphInfo,
} from '@/modules/main/api/db'

echarts.use([
  BarChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  CanvasRenderer,
])

// ==================== Tab 状态 ====================
type DbTab = 'rel' | 'vector' | 'cache' | 'graph'
const activeTab = ref<DbTab>('rel')
/** 已加载过的 tab(懒加载,切换时首次拉取) */
const loadedTabs = new Set<DbTab>()

const relLoading = ref(false)
const vectorLoading = ref(false)
const cacheLoading = ref(false)
const graphLoading = ref(false)

const keyword = ref('')
const tableList = ref<DbTableInfo[]>([])
const vectorInfo = ref<DbVectorInfo | null>(null)
const cacheInfo = ref<DbCacheInfo | null>(null)
const graphInfo = ref<DbGraphInfo | null>(null)

// ==================== 关系数据库 ====================
const barRef = ref<HTMLElement>()
const pieRef = ref<HTMLElement>()
let barChart: echarts.ECharts | null = null
let pieChart: echarts.ECharts | null = null

/** 图表主题色 */
const CHART_COLORS = [
  '#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#8d6ceb',
  '#36a3f7', '#00bfa5', '#ffb35c', '#f0609e', '#7f8fa6',
]

/** 按 row_count 取前 N 的表 */
const topTables = computed(() =>
  [...tableList.value].sort((a, b) => b.row_count - a.row_count),
)

/** 渲染柱状图(TOP10 数据条数) */
const renderBar = () => {
  if (!barRef.value) return
  const top = topTables.value.slice(0, 10).reverse()
  barChart ??= echarts.init(barRef.value)
  barChart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      valueFormatter: (v: unknown) => Number(v).toLocaleString(),
    },
    grid: { left: 8, right: 32, top: 8, bottom: 8, containLabel: true },
    xAxis: {
      type: 'value',
      axisLabel: { formatter: (v: number) => (v >= 1000 ? `${v / 1000}k` : String(v)), color: 'var(--el-text-color-secondary)' },
      splitLine: { lineStyle: { type: 'dashed', color: 'var(--el-border-color-lighter)' } },
    },
    yAxis: {
      type: 'category',
      data: top.map(t => t.name),
      axisLabel: { fontSize: 11, color: 'var(--el-text-color-secondary)' },
    },
    series: [{
      type: 'bar',
      data: top.map((t, i) => ({
        value: t.row_count,
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
          color: CHART_COLORS[(top.length - 1 - i) % CHART_COLORS.length],
        },
      })),
      barMaxWidth: 18,
      label: {
        show: true,
        position: 'right',
        formatter: ({ value }: { value: number }) => value.toLocaleString(),
        fontSize: 11,
        color: 'var(--el-text-color-secondary)',
      },
    }],
  })
}

/** 渲染环形图(数据量占比) */
const renderPie = () => {
  if (!pieRef.value) return
  const top = topTables.value.filter(t => t.row_count > 0)
  const head = top.slice(0, 8)
  const restRows = top.slice(8).reduce((s, t) => s + t.row_count, 0)
  const data = head.map((t, i) => ({
    name: t.name,
    value: t.row_count,
    itemStyle: { color: CHART_COLORS[i % CHART_COLORS.length] },
  }))
  if (restRows > 0) {
    data.push({ name: '其他', value: restRows, itemStyle: { color: 'var(--el-border-color)' } })
  }
  pieChart ??= echarts.init(pieRef.value)
  pieChart.setOption({
    tooltip: {
      trigger: 'item',
      valueFormatter: (v: unknown) => Number(v).toLocaleString(),
    },
    legend: {
      orient: 'vertical',
      right: 8,
      top: 'middle',
      icon: 'circle',
      itemWidth: 8,
      itemHeight: 8,
      textStyle: { fontSize: 11, color: 'var(--el-text-color-secondary)' },
    },
    series: [{
      type: 'pie',
      center: ['35%', '50%'],
      radius: ['45%', '72%'],
      data,
      label: { show: false },
      itemStyle: { borderRadius: 4, borderColor: 'var(--el-bg-color)', borderWidth: 2 },
      emphasis: {
        label: { show: false },
        scaleSize: 6,
      },
    }],
  })
}

/** 数据变化后重绘图表 */
watch(tableList, () => nextTick(() => {
  renderBar()
  renderPie()
}))

/** 窗口尺寸变化时自适应 */
const handleResize = () => {
  barChart?.resize()
  pieChart?.resize()
}

/** 总记录数 */
const totalRows = computed(() =>
  tableList.value.reduce((sum, t) => sum + (t.row_count || 0), 0),
)

/** 全库最近一次数据更新时间 */
const lastUpdatedOverall = computed(() => {
  const times = tableList.value
    .map(t => t.last_updated)
    .filter((t): t is string => !!t)
    .sort()
  return times.length ? fmtTime(times[times.length - 1]) : ''
})

/** 格式化时间:YYYY-MM-DD HH:mm */
const fmtTime = (iso: string) => {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 是否为今天更新 */
const isToday = (iso: string) => {
  const d = new Date(iso)
  const now = new Date()
  return d.getFullYear() === now.getFullYear()
    && d.getMonth() === now.getMonth()
    && d.getDate() === now.getDate()
}

/** 最近 24h 内有更新的表行高亮 */
const rowClassName = ({ row }: { row: DbTableInfo }) =>
  row.last_updated && isToday(row.last_updated) ? 'row-active' : ''

const fetchTables = async () => {
  try {
    relLoading.value = true
    tableList.value = await listDbTables(keyword.value)
    loadedTabs.add('rel')
  } catch (error) {
    console.error('获取数据表清单失败:', error)
    ElMessage.error('获取数据表清单失败')
  } finally {
    relLoading.value = false
  }
}

// ==================== 向量数据库 ====================
const vectorTables = computed(() => vectorInfo.value?.tables ?? [])
const totalVectors = computed(() =>
  vectorTables.value.reduce((sum, t) => sum + (t.row_count || 0), 0),
)

const fetchVector = async () => {
  try {
    vectorLoading.value = true
    vectorInfo.value = await listVectorTables()
    loadedTabs.add('vector')
  } catch (error) {
    console.error('获取向量库信息失败:', error)
    ElMessage.error('获取向量库信息失败')
  } finally {
    vectorLoading.value = false
  }
}

// ==================== 缓存/图数据库 ====================
const fetchCache = async () => {
  try {
    cacheLoading.value = true
    cacheInfo.value = await getCacheInfo()
    loadedTabs.add('cache')
  } catch (error) {
    console.error('获取缓存信息失败:', error)
    ElMessage.error('获取缓存信息失败')
  } finally {
    cacheLoading.value = false
  }
}

/** 图库信息键值对(剔除空值后渲染) */
const graphEntries = computed(() =>
  Object.entries(graphInfo.value ?? {}).filter(([, v]) => v !== null && v !== undefined),
)

const fetchGraph = async () => {
  try {
    graphLoading.value = true
    graphInfo.value = await getGraphInfo()
    loadedTabs.add('graph')
  } catch (error) {
    console.error('获取图数据库信息失败:', error)
    ElMessage.error('获取图数据库信息失败')
  } finally {
    graphLoading.value = false
  }
}

// ==================== Tab 调度 ====================
/** 按当前 tab 拉取对应数据 */
const fetchActive = async () => {
  switch (activeTab.value) {
    case 'rel': return fetchTables()
    case 'vector': return fetchVector()
    case 'cache': return fetchCache()
    case 'graph': return fetchGraph()
  }
}

/** 切换 tab:首次进入懒加载,回到关系库时重绘图表适配宽度 */
const handleTabChange = () => {
  if (!loadedTabs.has(activeTab.value)) {
    fetchActive()
  }
  nextTick(handleResize)
}

onMounted(async () => {
  window.addEventListener('resize', handleResize)
  await fetchTables()
  // 数据为空时也初始化图表(显示空坐标)
  await nextTick()
  renderBar()
  renderPie()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  barChart?.dispose()
  pieChart?.dispose()
  barChart = null
  pieChart = null
})
</script>

<style scoped>
/* 概览统计卡片 */
.stat-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.stat-card {
  flex: 1;
  min-width: 180px;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 20px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  transition: box-shadow 0.2s;
}

.stat-card:hover {
  box-shadow: var(--el-box-shadow-light);
}

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 8px;
  flex-shrink: 0;
}

.icon-blue {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.icon-green {
  color: var(--el-color-success);
  background: var(--el-color-success-light-9);
}

.icon-orange {
  color: var(--el-color-warning);
  background: var(--el-color-warning-light-9);
}

.icon-purple {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  line-height: 1.3;
  font-variant-numeric: tabular-nums;
}

.stat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

/* 卡片头部标题 */
.card-head {
  font-size: 14px;
  font-weight: 600;
}

/* 图表区 */
.chart-row {
  display: flex;
  gap: 16px;
}

.chart-card {
  flex: 1;
  min-width: 0;
}

.chart-box {
  width: 100%;
  height: 300px;
}

/* 文本色工具类 */
.text-muted {
  color: var(--el-text-color-secondary);
}

.text-subtle {
  color: var(--el-text-color-placeholder);
}

/* 最后更新单元格:时间 + 今天标签 */
.time-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-variant-numeric: tabular-nums;
}

/* 今日有更新的表行背景 */
:deep(.el-table .row-active) {
  background: var(--el-color-success-light-9);
}
</style>
