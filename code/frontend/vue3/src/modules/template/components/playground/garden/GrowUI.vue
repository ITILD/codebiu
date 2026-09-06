<template>
  <!-- 生长式 UI: 功能不一次性铺开, 而是随使用"长"出来 —— 渐进式披露 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <div class="flex-1">
      <!-- 花圃舞台: 点击播种 -->
      <div
        class="relative h-56 cursor-crosshair overflow-hidden rounded-md border border-[var(--el-border-color-light)] transition-colors duration-500"
        :class="SEASONS[state.season].cls"
        @click="plant"
      >
        <!-- 已种下的植物: 出生时弹性放大 -->
        <span
          v-for="p in state.plants"
          :key="p.id"
          class="gdn-plant absolute text-xl"
          :style="{ left: `${p.x}%`, top: `${p.y}%` }"
        >
          {{ p.icon }}
        </span>
        <!-- 浇水的雨滴 -->
        <template v-if="raining">
          <span v-for="i in 10" :key="`d-${i}`" class="gdn-drop absolute text-sm" :style="{ left: `${5 + i * 9}%` }">💧</span>
        </template>
        <!-- 空圃提示 -->
        <p v-if="!state.plants.length" class="absolute inset-0 flex items-center justify-center text-sm text-[var(--el-text-color-secondary)]">
          点击任意位置, 种下第一株植物
        </p>
      </div>

      <!-- XP 与工具条: 工具随里程碑解锁 -->
      <div class="mt-3 space-y-2">
        <div class="flex items-center gap-2">
          <span class="text-xs text-[var(--el-text-color-secondary)]">园艺 XP</span>
          <div class="relative h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--el-fill-color-dark)]">
            <div class="h-full bg-[var(--el-color-primary)] transition-all duration-300" :style="{ width: `${Math.min(100, (state.plants.length / 12) * 100)}%` }" />
          </div>
          <span class="text-xs text-[var(--el-text-color-secondary)]">{{ state.plants.length }}/12</span>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <template v-for="tool in tools" :key="tool.key">
            <el-tooltip v-if="tool.unlocked" :content="tool.hint" placement="top">
              <el-button size="small" @click="tool.run">{{ tool.label }}</el-button>
            </el-tooltip>
            <span v-else class="inline-flex items-center gap-1 rounded border border-dashed border-[var(--el-border-color)] px-3 py-1 text-xs text-[var(--el-text-color-secondary)]">
              🔒 {{ tool.label }} · 再种 {{ tool.need - state.plants.length }} 株解锁
            </span>
          </template>
        </div>
      </div>
    </div>

    <!-- 说明 -->
    <div class="w-full shrink-0 space-y-1 lg:w-56">
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        渐进式披露(progressive disclosure): 新手看到的界面越小越好, 功能在"用得到时"才出现。
        这里浇花/修剪/换季三个工具分别在 3/6/10 XP 后"生长"出来, 解锁前以占位告诉用户"再往前一步有什么"。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// 生长式 UI(garden.bradwoods.io/notes/design/user-driven-ui):
// 里程碑解锁工具 + 占位预告, 兼具引导与激励
/** 一株植物 */
interface Plant {
  id: number
  x: number
  y: number
  icon: string
}

/** 工具定义 */
interface Tool {
  key: string
  label: string
  hint: string
  need: number
  unlocked: boolean
  run: () => void
}

/** 季节定义 */
const SEASONS = [
  { name: '春', cls: 'bg-[#eef4e4]' },
  { name: '夏', cls: 'bg-[#e2f0e9]' },
  { name: '秋', cls: 'bg-[#f4ecdd]' },
  { name: '冬', cls: 'bg-[#e9e9ee]' },
] as const

/** 花圃状态 */
const state = reactive({ plants: [] as Plant[], season: 0 })

/** 自增 id */
let seq = 0

/** 是否正在下雨 */
const raining = ref(false)

/** 花朵图标池 */
const FLOWERS = ['🌸', '🌼', '🌻', '🌺', '🪻']

/** 播种: 在点击处种下一株(带落点抖动) */
function plant(e: MouseEvent) {
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  seq += 1
  state.plants.push({
    id: seq,
    x: ((e.clientX - rect.left) / rect.width) * 100,
    y: ((e.clientY - rect.top) / rect.height) * 100,
    icon: seq % 3 === 0 ? FLOWERS[seq % FLOWERS.length] : '🌱',
  })
}

/** 浇水: 下雨并让部分幼苗开花 */
function water() {
  if (raining.value) return
  raining.value = true
  setTimeout(() => (raining.value = false), 900)
  state.plants.filter((p) => p.icon === '🌱').slice(-3).forEach((p, i) => {
    setTimeout(() => (p.icon = FLOWERS[(p.id + i) % FLOWERS.length]), 300 + i * 250)
  })
}

/** 修剪: 移除最新一株 */
function prune() {
  state.plants.pop()
}

/** 换季 */
function shiftSeason() {
  state.season = (state.season + 1) % SEASONS.length
}

/** 工具条: need 达到即解锁 */
const tools = computed<Tool[]>(() => [
  { key: 'water', label: '浇水', hint: '让幼苗开花', need: 3, unlocked: state.plants.length >= 3, run: water },
  { key: 'prune', label: '修剪', hint: '移走最后一株', need: 6, unlocked: state.plants.length >= 6, run: prune },
  { key: 'season', label: '换季', hint: '切换花圃季节', need: 10, unlocked: state.plants.length >= 10, run: shiftSeason },
])
</script>

<style scoped>
/* 植物出生: 弹性放大 */
.gdn-plant {
  animation: gdn-sprout 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) both;
  transform: translate(-50%, -50%);
}

/* 雨滴: 从顶部坠落 */
.gdn-drop {
  top: -10%;
  animation: gdn-fall 0.8s linear both;
}

@keyframes gdn-sprout {
  from { transform: translate(-50%, -50%) scale(0); }
  to { transform: translate(-50%, -50%) scale(1); }
}

@keyframes gdn-fall {
  from { transform: translateY(0); opacity: 1; }
  to { transform: translateY(240px); opacity: 0.2; }
}
</style>
