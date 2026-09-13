<template>
  <!-- 宝宝取名独立应用页: 左侧配置区(宝宝信息+辅助信息) + 右侧结果区(参考信息+名字卡片) -->
  <div class="baby-name-page" :class="{ 'girl-mode': isGirl }" flex flex-col h-app w-full bg-note-paper overflow-hidden>
    <!-- 页头: 标语 + 模型选择 -->
    <header bg-note-gradient px-4 md:px-6 py-3.5 border-b border-note shrink-0>
      <div flex items-center gap-3 flex-wrap>
        <div>
          <h1 text-lg md:text-xl font-bold text-note style="font-family: var(--note-font-hand)">
            {{ isGirl ? '🌸 宝宝取名 · 小棉袄专属' : '🌱 宝宝取名' }}
          </h1>
          <p text-xs text-note-sub mt-0.5>
            经典算法严格推算生辰参考, AI 结合民俗与神话为宝宝起一个好名字
          </p>
        </div>
        <div ml-auto flex items-center gap-2>
          <!-- 起名模型只读展示: 直接使用用户设置里的默认 chat 模型, 页面不提供切换 -->
          <span text-xs text-note-sub>起名模型</span>
          <span
            class="note-transition inline-flex items-center gap-1.5 rounded-lg border border-note-green bg-note-tint px-2.5 py-1"
            text-xs font-medium text-note
          >
            <span class="i-ep-cpu" text-sm text-note-green />
            {{ modelName || '未配置(请在模型设置中设默认 chat 模型)' }}
          </span>
        </div>
      </div>
    </header>

    <!-- 主体: 双区布局(移动端上下堆叠) -->
    <div flex flex-1 min-h-0 flex-col lg:flex-row overflow-hidden>
      <!-- 左侧配置区 -->
      <aside w-full lg:w-115 shrink-0 overflow-y-auto p-4 space-y-3 lg:border-r border-note border-b lg:border-b-0>
        <!-- 宝宝信息 -->
        <section class="page-card">
          <div card-toolbar>
            <span text-sm font-bold text-note>👶 宝宝信息</span>
          </div>
          <el-form :model="formData" label-width="76px">
            <el-form-item label="姓氏" required>
              <el-input v-model="formData.surname" placeholder="如: 王" maxlength="4" :disabled="generating" />
            </el-form-item>
            <el-form-item label="性别" required>
              <el-radio-group v-model="formData.gender" :disabled="generating">
                <el-radio-button value="girl">女宝</el-radio-button>
                <el-radio-button value="boy">男宝</el-radio-button>
                <el-radio-button value="unknown">未知</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="出生日期" required>
              <el-date-picker v-model="formData.birth_date" type="date" placeholder="公历出生日期" format="YYYY-MM-DD"
                value-format="YYYY-MM-DD" :disabled="generating" w-full />
            </el-form-item>
            <el-form-item label="出生时辰" required>
              <el-time-picker v-model="formData.birth_time" placeholder="出生时间" format="HH:mm" value-format="HH:mm"
                :disabled="generating" w-full />
            </el-form-item>
            <el-form-item label="名字字数">
              <el-input-number v-model="formData.name_length" :min="1" :max="3" :step="1" :disabled="generating" w-full />
            </el-form-item>
          </el-form>
        </section>

        <!-- 取名辅助信息(参考体系配置 + 其他要求) -->
        <section class="page-card">
          <div card-toolbar>
            <span text-sm font-bold text-note>🧭 取名辅助信息</span>
            <el-tooltip content="按宝宝信息严格推算选中的参考体系" placement="top">
              <el-button size="small" type="primary" plain :loading="calculating"
                :disabled="!canCalculate || generating || !!catalogError" @click="handleCalculate">
                推测参考信息
              </el-button>
            </el-tooltip>
          </div>

          <!-- 参考体系多选(加载失败时给可见错误态与重试, 避免静默空白) -->
          <ReferencePicker v-if="catalog.length" v-model="selectedRefs" :catalog="catalog"
            :disabled="generating" />
          <div v-else-if="catalogError" rounded-xl border border-dashed border-note bg-note-soft p-3
            text-center>
            <div text-xs text-note-sub mb-2>参考体系目录加载失败: {{ catalogError }}</div>
            <div text-10px text-note-sub mb-2>请确认后端服务已重启至最新版本(life 模块新端点)</div>
            <el-button size="small" type="primary" plain @click="loadCatalog">重试</el-button>
          </div>
          <div v-else flex justify-center py-3>
            <el-icon class="is-loading text-note-green"><Loading /></el-icon>
          </div>

          <!-- 其他要求(由宝宝信息迁移至此) -->
          <el-form label-width="76px" class="mt-3">
            <el-form-item label="其他要求">
              <el-input v-model="formData.other" type="textarea" :rows="2" maxlength="200"
                placeholder="如: 避免用字、偏好的风格或寓意(选填)" :disabled="generating" />
            </el-form-item>
          </el-form>
        </section>

        <!-- 起名操作 -->
        <section class="page-card">
          <div flex gap-2>
            <el-button type="primary" class="flex-1" :loading="generating && !isMore"
              :disabled="!canGenerate" @click="handleGenerate(20)">
              {{ generating && !isMore ? '起名中...' : '开始起名(20个)' }}
            </el-button>
            <el-button type="primary" plain class="flex-1" :loading="generating && isMore"
              :disabled="!canGenerateMore" @click="handleGenerate(10, true)">
              {{ generating && isMore ? '生成中...' : '生成更多(10个)' }}
            </el-button>
          </div>
          <div v-if="evaluatedNames.length" text-center text-xs text-note-sub mt-2>
            已生成 {{ evaluatedNames.length }} 个名字, "生成更多"自动避开已出名字
          </div>
        </section>
      </aside>

      <!-- 右侧结果区 -->
      <main flex-1 min-w-0 overflow-y-auto p-4 space-y-3>
        <!-- 推测失败错误态(含后端 detail, 便于定位后端未重启/接口异常) -->
        <section v-if="refError" class="page-card">
          <el-alert type="error" :closable="false">
            <template #title>参考信息推算失败</template>
            <div flex items-center gap-2 flex-wrap>
              <span text-xs>{{ refError }}</span>
              <el-button size="small" type="primary" plain :disabled="!canCalculate || calculating"
                @click="handleCalculate">重试</el-button>
            </div>
          </el-alert>
        </section>

        <!-- 推测的参考信息(严格计算结果) -->
        <section v-if="refResult" class="page-card">
          <div card-toolbar>
            <span text-sm font-bold text-note>🔮 推测的参考信息</span>
            <span text-xs text-note-sub>经典算法严格推算, 起名时自动遵循</span>
          </div>
          <ReferencePanel :result="refResult" :loading="calculating" />
        </section>

        <!-- 起名过程(流式, 限高滚动 + 自动跟随最新内容) -->
        <section v-if="generateMarkdown" class="page-card">
          <div card-toolbar>
            <span text-sm font-bold text-note>✍️ 起名思路</span>
            <el-icon v-if="generating" class="is-loading text-note-green"><Loading /></el-icon>
          </div>
          <div ref="markdownRef" prose text-sm max-w-none max-h-100 overflow-y-auto
            v-html="renderMarkdown(generateMarkdown)" />
        </section>

        <!-- 推荐名字(程序评定) -->
        <section class="page-card">
          <div card-toolbar>
            <span text-sm font-bold text-note>🏷️ 推荐名字</span>
            <el-button v-if="evaluatedNames.length" size="small" text bg :disabled="generating"
              @click="clearAll">清空</el-button>
          </div>
          <NameResultList :names="evaluatedNames" :show-sancai="selectedRefs.includes('sancai')" />
        </section>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
/** 宝宝取名页: 宝宝信息 + 取名辅助信息(民俗/神话参考多选) → 严格推算 → AI 流式起名 → 程序评定 */
import { type PaginationParams } from '@/common/types/common'
import type { ModelConfig } from '@/modules/ai/types/model_config'
import { listModelConfigs } from '@/modules/ai/api/model_config'
import { marked } from 'marked'
import { sanitizeHtml } from '@/common/utils/sanitize'
import ReferencePicker from '../components/ReferencePicker.vue'
import ReferencePanel from '../components/ReferencePanel.vue'
import NameResultList from '../components/NameResultList.vue'
import { getReferenceCatalog, calculateReference, generateBabyNamesStream } from '../api/baby_name'
import type {
  NameInfoPredictFullRequest,
  GenderEnum,
  FolkReferenceItem,
  ReferenceKey,
  ReferenceCalculateResult,
  EvaluatedName,
} from '../types/baby_name'

// 渲染 Markdown 内容(先消毒再渲染, LLM 输出不可信)
const renderMarkdown = (content: string) => sanitizeHtml(marked.parse(content) as string)

// ==================== 模型(只读展示: 直接使用用户设置里的默认 chat 模型, 页面不切换) ====================
const model_id = ref('')
const tableData = ref<ModelConfig[]>([])
/** 当前默认 chat 模型的展示名(display_name 优先, 留空取 model) */
const modelName = computed(() => {
  const m = tableData.value.find((x) => x.id === model_id.value)
  return m ? m.display_name || m.model : ''
})

// ==================== 宝宝信息 ====================
const formData = ref<NameInfoPredictFullRequest>({
  surname: '',
  gender: 'unknown' as GenderEnum,
  birth_date: '',
  birth_time: '',
  name_length: 2,
  other: '',
  model_id: '',
})

/** 女宝模式: 页面整体切换樱粉柔和主题 */
const isGirl = computed(() => formData.value.gender === 'girl')

// ==================== 参考体系 ====================
const catalog = ref<FolkReferenceItem[]>([])
const selectedRefs = ref<ReferenceKey[]>([])
const refResult = ref<ReferenceCalculateResult | null>(null)
const calculating = ref(false)
const catalogError = ref('') // 参考体系目录加载失败信息(空=正常)
const refError = ref('') // 参考信息推算失败信息(空=正常)

/** 加载参考体系目录(供多选卡片; 失败显示重试按钮) */
const loadCatalog = async () => {
  catalogError.value = ''
  try {
    catalog.value = await getReferenceCatalog()
    // 默认选中经典严格计算项
    selectedRefs.value = catalog.value.filter((r) => r.strict).map((r) => r.key)
  } catch (e) {
    catalog.value = []
    selectedRefs.value = []
    catalogError.value = e instanceof Error ? e.message : '网络异常'
    console.error('参考体系目录加载失败:', e)
  }
}

/** 基础信息是否可推算(姓氏+生日+时辰) */
const canCalculate = computed(
  () => !!(formData.value.surname && formData.value.birth_date && formData.value.birth_time),
)
/** 是否可起名(基础信息 + 已选参考; 模型可留空, 后端自动兜底默认 chat 模型) */
const canGenerate = computed(() => canCalculate.value && selectedRefs.value.length > 0)
/** "生成更多"需已有结果 */
const canGenerateMore = computed(() => canGenerate.value && evaluatedNames.value.length > 0)

/** 推测参考信息: 严格计算选中的参考体系 */
const handleCalculate = async () => {
  if (!canCalculate.value || calculating.value) return
  calculating.value = true
  refError.value = ''
  try {
    refResult.value = await calculateReference({
      surname: formData.value.surname,
      gender: formData.value.gender,
      birth_date: formData.value.birth_date,
      birth_time: formData.value.birth_time,
      references: selectedRefs.value,
    })
  } catch (e) {
    refResult.value = null
    // 失败时在结果区展示错误态(含后端 404/500 的 detail), 避免点击后无任何反馈
    refError.value = e instanceof Error ? e.message : '推算失败, 请重试'
    console.error('推算参考信息失败:', e)
  } finally {
    calculating.value = false
  }
}

// ==================== 起名生成 ====================
const generating = ref(false)
const isMore = ref(false) // 当前是否为"生成更多"批次
const generateMarkdown = ref('') // 当批 LLM 流式 markdown
const evaluatedNames = ref<EvaluatedName[]>([]) // 多批次累计的名字(评定后)

// 流式生成时 markdown 容器自动滚动到最新内容
const markdownRef = ref<HTMLElement | null>(null)
watch(generateMarkdown, async () => {
  if (!generating.value || !markdownRef.value) return
  await nextTick()
  markdownRef.value.scrollTo({ top: markdownRef.value.scrollHeight })
})

/** 起名/生成更多: SSE 流式生成 + 程序评定结果累加(防重复) */
const handleGenerate = async (count: number, more = false) => {
  if (generating.value || !canGenerate.value) return
  // 未推算过参考信息时自动补一次(起名遵循严格计算结果)
  if (!refResult.value && selectedRefs.value.length) await handleCalculate()

  isMore.value = more
  generating.value = true
  generateMarkdown.value = ''
  if (!more) evaluatedNames.value = [] // 全新生成时清空历史批次

  try {
    await generateBabyNamesStream(
      {
        ...formData.value,
        model_id: model_id.value,
        references: selectedRefs.value,
        count,
        // 生成更多时传入已有名字防重复
        exclude_names: more ? evaluatedNames.value.map((n) => n.name) : [],
      },
      (nodeName, content) => {
        if (nodeName === 'generate_name_result') {
          // LLM 流式 markdown(每批重置)
          generateMarkdown.value += content
        } else if (nodeName === 'names_evaluated') {
          // 程序评定清单: 追加并按名字去重
          try {
            const batch: EvaluatedName[] = JSON.parse(content)
            const exist = new Set(evaluatedNames.value.map((n) => n.name))
            evaluatedNames.value.push(...batch.filter((n) => !exist.has(n.name)))
          } catch (e) {
            console.warn('解析评定结果失败:', e)
          }
        }
        // calc_* 严格计算节点: 结果已由"推测参考信息"结构化展示, 此处忽略
      },
      (error) => {
        ElMessage.error(`起名失败: ${error}`)
        generating.value = false
      },
      () => {
        generating.value = false
        ElMessage.success(more ? '已生成更多名字' : '起名完成')
      },
    )
  } catch (e) {
    console.error('起名失败:', e)
    ElMessage.error('起名失败, 请重试')
    generating.value = false
  }
}

/** 清空全部结果 */
const clearAll = () => {
  evaluatedNames.value = []
  generateMarkdown.value = ''
}

// ==================== 初始化 ====================
onMounted(() => {
  // 并行加载: 起名模型列表(仅 chat 类, 取用户设置的默认模型展示) + 参考体系目录
  const params = { page: 1, size: 100, model_type: 'chat' } as PaginationParams
  listModelConfigs(params)
    .then((res) => {
      tableData.value = res.items
      // 直接使用用户设置里的默认 chat 模型(is_default), 无默认则取列表第一个
      const preferred = res.items.find((m) => m.is_default) ?? res.items[0]
      if (preferred) model_id.value = preferred.id
    })
    .catch((e) => console.error('模型列表加载失败:', e))
  loadCatalog()
})
</script>

<style scoped>
/* ==================== 女宝樱粉主题(覆盖页面作用域的 note 变量与组件主色) ==================== */
/* 亮色: 樱粉纸面 + 玫瑰强调 */
.baby-name-page.girl-mode {
  --note-green: #e39cb2;
  --note-green-deep: #c97a94;
  --note-paper: #fdf8fa;
  --note-soft: #faf1f5;
  --note-tint: #fbe9f0;
  --note-border: #f0dfe6;
  --note-border-green: #e7bccb;
  --note-text: #5c4450;
  --note-sub: #8a6b78;
  --note-accent: #c2627f;
  --note-shadow: 0 0 0 1px rgba(226, 158, 178, 0.18), 0 2px 12px rgba(226, 158, 178, 0.16);
  --note-shadow-hover: 0 0 0 1px rgba(226, 158, 178, 0.2), 0 8px 24px rgba(226, 158, 178, 0.26);
  --note-grad-from: #fbe9f0;
  --note-grad-via: #fdf4f7;
  --note-grad-to: #f8dfe8;
  --note-scrollbar: rgba(226, 158, 178, 0.35);
  --el-color-primary: #d97f9c;
  --el-color-primary-light-3: #e39cb2;
  --el-color-primary-light-5: #ecb8ca;
  --el-color-primary-light-7: #f3d3df;
  --el-color-primary-light-8: #f7e0e8;
  --el-color-primary-light-9: #faecf1;
  --el-color-primary-dark-2: #c2627f;
  --el-border-color: #eddfe5;
  --el-text-color-primary: #5c4450;
  --el-text-color-regular: #8a6b78;
}

/* 暗色: 深玫瑰夜色 */
html.dark .baby-name-page.girl-mode {
  --note-green: #d88ba6;
  --note-green-deep: #e5a8bd;
  --note-paper: #170e12;
  --note-soft: #241519;
  --note-card: #2a1a20;
  --note-tint: #3a222b;
  --note-border: #3d2830;
  --note-border-green: #6b4053;
  --note-text: #f2dde5;
  --note-sub: #c5a1ae;
  --note-accent: #e9aebf;
  --note-grad-from: #2a1a20;
  --note-grad-via: #1d1216;
  --note-grad-to: #3a222b;
  --el-color-primary: #d88ba6;
  --el-color-primary-light-3: #c27a92;
  --el-color-primary-light-5: #9c5f73;
  --el-color-primary-light-7: #6d4251;
  --el-color-primary-light-8: #573643;
  --el-color-primary-light-9: #402833;
  --el-color-primary-dark-2: #e5a8bd;
}
</style>
