<template>
  <div p-4 md:p-6 w-full class="server-status-page">
    <!-- 顶部操作栏: 标题 + 自动刷新开关 + 手动刷新 -->
    <div mb-4 flex flex-wrap items-center justify-between gap-2>
      <div>
        <h2 text-lg font-bold text-note>服务状态</h2>
        <p text-xs text-note-sub mt-1>
          🌿 数据来自后端 60 秒缓存，最后更新: {{ lastUpdateText }}
        </p>
      </div>
      <div flex items-center gap-2>
        <el-switch v-model="autoRefresh" active-text="自动刷新" inactive-text="暂停" />
        <el-tooltip content="立即刷新(实时读取硬件状态)">
          <el-button :icon="Refresh" :loading="loading" circle />
        </el-tooltip>
      </div>
    </div>

    <!-- 概览卡片: 主机型号 / 挂载路由 / 网络 -->
    <div mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3>
      <div p-4 rounded-lg bg-note-card border-note shadow-note>
        <p text-xs text-note-sub>主机型号</p>
        <p mt-2 text-xl font-bold text-note-green>{{ sysInfo || '未知' }}</p>
      </div>
      <div p-4 rounded-lg bg-note-card border-note shadow-note>
        <p text-xs text-note-sub>挂载路由数量</p>
        <p mt-2 text-xl font-bold text-note-green>{{ mountCount }}</p>
      </div>
      <div p-4 rounded-lg bg-note-card border-note shadow-note>
        <p text-xs text-note-sub>网络连通性</p>
        <p mt-2 text-xl font-bold :class="networkOk ? 'text-note-green' : 'text-red-500'">
          {{ networkOk ? '正常' : '异常' }}
        </p>
      </div>
    </div>

    <div v-loading="loading" grid gap-4 lg:grid-cols-2>
      <!-- 硬件状态: CPU / 内存 / 磁盘 -->
      <div p-4 rounded-lg bg-note-card border-note shadow-note>
        <h3 mb-4 font-bold text-note>🖥️ 硬件状态</h3>
        <template v-if="hardware">
          <!-- CPU -->
          <div mb-4>
            <div mb-1 flex items-center justify-between text-sm text-note>
              <span>CPU 使用率</span>
              <span text-note-sub>{{ hardware.cpu.cores }} 核 {{ hardware.cpu.threads }} 线程</span>
            </div>
            <el-progress :percentage="round(hardware.cpu.percent)" :color="progressColor" />
          </div>
          <!-- 内存 -->
          <div mb-4>
            <div mb-1 flex items-center justify-between text-sm text-note>
              <span>内存</span>
              <span text-note-sub>
                {{ hardware.memory.used.toFixed(1) }} / {{ hardware.memory.total.toFixed(1) }} GB
              </span>
            </div>
            <el-progress :percentage="round(hardware.memory.percent)" :color="progressColor" />
          </div>
          <!-- 磁盘 -->
          <div>
            <div mb-1 flex items-center justify-between text-sm text-note>
              <span>磁盘</span>
              <span text-note-sub>
                {{ hardware.disk.used.toFixed(1) }} / {{ hardware.disk.total.toFixed(1) }} GB
              </span>
            </div>
            <el-progress :percentage="round(hardware.disk.percent)" :color="progressColor" />
          </div>
        </template>
        <el-empty v-else description="暂无硬件数据" :image-size="60" />
      </div>

      <!-- GPU 状态 -->
      <div p-4 rounded-lg bg-note-card border-note shadow-note>
        <h3 mb-4 font-bold text-note>🎛️ GPU 状态</h3>
        <template v-if="hardware && hardware.gpu.length > 0">
          <div v-for="gpu in hardware.gpu" :key="gpu.id" mb-4 p-3 rounded bg-note-soft last:mb-0>
            <div flex items-center justify-between text-sm text-note>
              <span font-bold>{{ gpu.name }}</span>
              <el-tag size="small" type="info">{{ gpu.vendor }}</el-tag>
            </div>
            <div mt-2 text-xs text-note-sub>
              显存 {{ gpu.used }} / {{ gpu.total }} MB · 温度 {{ gpu.temp }}°C
            </div>
            <el-progress mt-2 :percentage="round(gpu.percent)" :color="progressColor" />
          </div>
        </template>
        <el-empty v-else description="未检测到 GPU" :image-size="60" />
      </div>

      <!-- 网络状态 -->
      <div p-4 rounded-lg bg-note-card border-note shadow-note lg:col-span-2>
        <h3 mb-4 font-bold text-note>🌐 网络状态</h3>
        <el-table :data="networkList" stripe w-full size="small">
          <el-table-column prop="url" label="目标地址" min-width="240" show-overflow-tooltip />
          <el-table-column label="连接状态" width="120" align="center">
            <template #default="{ row }">
              <el-tag :type="row.connect_success ? 'success' : 'danger'" size="small">
                {{ row.connect_success ? '已连接' : '连接失败' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="networkList.length === 0" description="暂无网络监测数据" :image-size="60" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getMountCount, getStatusCache, getSysInfo } from '@/api/main/status'
import type { HardwareStatus, NetworkStatus } from '@/types/main/status'

// 状态数据
const loading = ref(false)
const sysInfo = ref('')
const mountCount = ref(0)
const hardware = ref<HardwareStatus | null>(null)
const networkList = ref<NetworkStatus[]>([])
const lastUpdate = ref<Date | null>(null)

// 自动刷新开关(缓存60秒, 每60秒拉取一次)
const autoRefresh = ref(true)
let timer: ReturnType<typeof setInterval> | null = null

// 进度条颜色: 低负载苔绿, 高负载警示
const progressColor = [
  { color: '#6b9e78', percentage: 60 },
  { color: '#e6a23c', percentage: 85 },
  { color: '#f56c6c', percentage: 100 },
]

// 网络是否全部连通
const networkOk = computed(() => networkList.value.length > 0 && networkList.value.every(n => n.connect_success))

// 最后更新时间文案
const lastUpdateText = computed(() => {
  if (!lastUpdate.value) return '尚未获取'
  return lastUpdate.value.toLocaleTimeString('zh-CN')
})

// 数值取整(el-progress 需 0-100 整数)
const round = (v: number) => Math.round(v)

/** 拉取状态缓存 + 主机型号 + 挂载路由 */
const fetchData = async () => {
  try {
    loading.value = true
    const [cache, info, mounts] = await Promise.all([
      getStatusCache(),
      getSysInfo(),
      getMountCount(),
    ])
    hardware.value = cache.hardware
    networkList.value = cache.network ?? []
    sysInfo.value = info
    mountCount.value = Array.isArray(mounts) ? mounts.length : 0
    lastUpdate.value = new Date()
  } catch (error) {
    console.error('获取服务器状态失败:', error)
    ElMessage.error('获取服务器状态失败，请确认后端服务已启动')
  } finally {
    loading.value = false
  }
}

// 自动刷新定时器管理
const startTimer = () => {
  stopTimer()
  timer = setInterval(fetchData, 60_000)
}
const stopTimer = () => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}
watch(autoRefresh, (on) => (on ? startTimer() : stopTimer()))

onMounted(() => {
  fetchData()
  if (autoRefresh.value) startTimer()
})

onUnmounted(stopTimer)
</script>
