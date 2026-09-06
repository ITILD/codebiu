<template>
  <div p-4 md:p-6 w-full flex flex-col gap-4>
    <!-- 说明与操作 -->
    <div rounded-lg p-4 bg-note-card border border-note shadow-note flex flex-col gap-3>
      <div flex flex-wrap items-center gap-3>
        <div flex-1 min-w-0>
          <div text-base font-bold text-note>前端接口测试</div>
          <div text-xs text-note-sub mt-1>
            共 {{ cases.length }} 个接口用例, 与 src/modules/*/api/*.ts 自动校验覆盖。
            "全部执行"只跑无副作用的 GET 接口; 写操作与依赖真实资源的接口请单条执行。
            判定: 2xx 通过 / 401·403·422 警告 / 404 失败(资源型接口除外) / 5xx·网络错误 失败。
          </div>
        </div>
        <el-button type="primary" :loading="running" @click="runAll">
          <el-icon v-if="!running" mr-1><VideoPlay /></el-icon>
          {{ running ? `执行中 ${progress}/${autoCases.length}` : `全部执行(${autoCases.length})` }}
        </el-button>
        <el-button v-if="running" type="warning" @click="stopAll">停止</el-button>
        <el-button @click="reset">重置</el-button>
      </div>
      <!-- 批量执行进度条 -->
      <el-progress
        v-if="running || progress > 0"
        :percentage="Math.round((progress / Math.max(autoCases.length, 1)) * 100)"
        :stroke-width="8"
        :status="running ? undefined : 'success'"
      />
      <!-- 覆盖校验警告: api 模块存在未收录清单的接口函数 -->
      <el-alert v-if="uncoveredFns.length" type="warning" :closable="false" show-icon>
        <template #title>
          清单未覆盖 {{ uncoveredFns.length }} 个接口函数, 请在 data/cases.ts 补全:
          {{ uncoveredFns.map((u) => `${u.file}#${u.fn}`).join('、') }}
        </template>
      </el-alert>
    </div>

    <!-- 统计卡片: 手机 2 列 / 平板及以上 5 列 -->
    <div grid grid-cols-2 md:grid-cols-5 gap-3>
      <div
        v-for="card in statCards" :key="card.level"
        cursor-pointer rounded-lg p-3 bg-note-card border border-note shadow-note
        transition-colors hover:bg-note-tint
        :class="{ 'ring-2 ring-note': filterLevel === card.level }"
        @click="toggleLevelFilter(card.level)"
      >
        <div text-xs text-note-sub>{{ card.label }}</div>
        <div text-2xl font-bold mt-1 :class="card.color">{{ card.count }}</div>
      </div>
    </div>

    <!-- 过滤工具栏 -->
    <div flex flex-wrap items-center gap-3>
      <el-select v-model="filterModule" placeholder="全部模块" clearable w-40>
        <el-option v-for="m in moduleOptions" :key="m" :label="m" :value="m" />
      </el-select>
      <el-select v-model="filterLevel" placeholder="全部状态" clearable w-36>
        <el-option label="通过" value="pass" />
        <el-option label="警告" value="warn" />
        <el-option label="失败" value="fail" />
        <el-option label="跳过" value="skip" />
        <el-option label="未执行" value="idle" />
      </el-select>
      <el-input v-model="keyword" placeholder="搜索函数 / 路径" clearable w-60 />
      <div flex-1 />
      <span text-xs text-note-sub>当前显示 {{ filteredCases.length }} / {{ cases.length }}</span>
    </div>

    <!-- 用例表格 -->
    <el-table :data="filteredCases" stripe w-full row-key="key">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div p-4 flex flex-col gap-2 bg-note-tint>
            <div text-xs text-note-sub>
              完整路径: <code text-note>{{ PREFIX + row.path }}</code>
              <template v-if="row.note"> · {{ row.note }}</template>
            </div>
            <div v-if="resultOf(row).snippet" text-xs>
              <div text-note-sub mb-1>响应预览:</div>
              <pre class="whitespace-pre-wrap break-all rounded p-2 bg-note-paper text-note text-xs leading-5">{{ resultOf(row).snippet }}</pre>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="levelTagType(resultOf(row).level)" size="small" effect="light">
            {{ levelLabel(resultOf(row).level) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="module" label="模块" width="110" show-overflow-tooltip />
      <el-table-column prop="fn" label="接口函数" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">
          <span text-xs>{{ row.fn }}</span>
        </template>
      </el-table-column>
      <el-table-column label="方法" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="methodTagType(row.method)" size="small" effect="plain">{{ row.method }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="path" label="路径" min-width="240" show-overflow-tooltip>
        <template #default="{ row }">
          <span text-xs font-mono>{{ row.path }}</span>
        </template>
      </el-table-column>
      <el-table-column label="耗时" width="80" align="center">
        <template #default="{ row }">
          <span v-if="resultOf(row).ms" text-xs text-note-sub>{{ resultOf(row).ms }}ms</span>
          <span v-else text-xs text-note-sub>-</span>
        </template>
      </el-table-column>
      <el-table-column label="结果说明" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <span text-xs :class="resultMessageClass(resultOf(row).level)">
            {{ resultOf(row).message || row.note || '-' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" align="center" :fixed="isMd ? 'right' : false">
        <template #default="{ row }">
          <el-button
            link type="primary" size="small"
            :disabled="resultOf(row).level === 'skip' || running"
            @click="runOne(row)"
          >
            执行
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
// 接口测试页面: 查看前端全部接口的连通性测试结果
import { computed, ref } from 'vue';
import { VideoPlay } from '@element-plus/icons-vue';
import { SysSettingStore } from '@/common/stores/sys';
import { API_CASES, caseKey, type ApiCase } from '../data/cases';
import { useApiTest, type CaseResult } from '../composables/useApiTest';

const sysSettingStore = SysSettingStore();
const isMd = computed(() => sysSettingStore.sysStyle.isMd);

const {
  results, running, progress, autoCases, stats, uncoveredFns,
  runAll, stopAll, runCase, reset,
} = useApiTest();

/** 请求前缀展示 */
const PREFIX = '/base_server';

/** 用例附带稳定 key 与结果访问 */
interface CaseRow extends ApiCase { key: string }
const cases: CaseRow[] = API_CASES.map((c) => ({ ...c, key: caseKey(c) }));

/** 单行结果(未执行时返回空闲占位) */
function resultOf(row: CaseRow): CaseResult {
  return results[row.key] ?? { level: 'idle', statusCode: null, message: '', ms: 0, snippet: '' };
}

// ==================== 统计卡片 ====================

const statCards = computed(() => [
  { level: 'pass', label: '通过', count: stats.value.pass, color: 'text-green-600' },
  { level: 'warn', label: '警告', count: stats.value.warn, color: 'text-amber-500' },
  { level: 'fail', label: '失败', count: stats.value.fail, color: 'text-red-500' },
  { level: 'skip', label: '跳过', count: stats.value.skip, color: 'text-note-sub' },
  { level: 'idle', label: '未执行', count: stats.value.idle, color: 'text-note' },
]);

// ==================== 过滤 ====================

const filterModule = ref('');
const filterLevel = ref('');
const keyword = ref('');

/** 模块下拉选项(清单去重) */
const moduleOptions = computed(() => [...new Set(cases.map((c) => c.module))]);

/** 点击统计卡切换状态过滤(再次点击取消) */
function toggleLevelFilter(level: string): void {
  filterLevel.value = filterLevel.value === level ? '' : level;
}

/** 按模块/状态/关键字过滤用例 */
const filteredCases = computed(() =>
  cases.filter((c) => {
    if (filterModule.value && c.module !== filterModule.value) return false;
    if (filterLevel.value && resultOf(c).level !== filterLevel.value) return false;
    if (keyword.value) {
      const kw = keyword.value.toLowerCase();
      if (!c.fn.toLowerCase().includes(kw) && !c.path.toLowerCase().includes(kw)) return false;
    }
    return true;
  }),
);

// ==================== 展示辅助 ====================

const LEVEL_LABELS: Record<string, string> = {
  idle: '未执行', running: '执行中', pass: '通过', warn: '警告', fail: '失败', skip: '跳过',
};
const LEVEL_TAG_TYPES: Record<string, string> = {
  idle: 'info', running: 'primary', pass: 'success', warn: 'warning', fail: 'danger', skip: 'info',
};
const METHOD_TAG_TYPES: Record<string, string> = {
  GET: 'success', POST: 'primary', PUT: 'warning', DELETE: 'danger',
};

function levelLabel(level: string): string {
  return LEVEL_LABELS[level] ?? level;
}
function levelTagType(level: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  return (LEVEL_TAG_TYPES[level] ?? 'info') as 'success' | 'warning' | 'danger' | 'info' | 'primary';
}
function methodTagType(method: string): 'success' | 'warning' | 'danger' | 'primary' {
  return (METHOD_TAG_TYPES[method] ?? 'info') as 'success' | 'warning' | 'danger' | 'primary';
}
function resultMessageClass(level: string): string {
  if (level === 'fail') return 'text-red-500';
  if (level === 'warn') return 'text-amber-500';
  if (level === 'pass') return 'text-green-600';
  return 'text-note-sub';
}

/** 单条执行 */
async function runOne(row: CaseRow): Promise<void> {
  await runCase(row);
}
</script>
