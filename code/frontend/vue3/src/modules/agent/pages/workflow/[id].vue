<template>
  <!-- 工作流可视化编辑器(全屏): 顶部工具栏 + 左节点面板 + 中画布 + 右属性面板 -->
  <div class="flex flex-col w-full h-[calc(100vh-3.5rem)] md:h-[calc(100vh-4rem)] overflow-hidden">
    <!-- 顶部工具栏 -->
    <header class="h-12 shrink-0 flex items-center gap-2 px-3 border-b border-note bg-note-card">
      <RouterLink
        to="/agent/manage"
        class="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-sm text-note-sub hover:bg-note-tint hover:text-note-green transition-colors"
      >
        <el-icon :size="14"><Back /></el-icon>
        返回
      </RouterLink>
      <span class="text-sm font-bold text-note truncate">{{ agent?.name || '工作流编辑器' }}</span>
      <el-tag v-if="agent && agent.agent_type !== 'workflow'" size="small" type="warning" effect="plain">
        简单智能体, 保存后切换为工作流
      </el-tag>
      <span class="flex-1" />
      <el-button size="small" text bg :loading="saving" @click="handleSave">
        <el-icon class="mr-1"><Finished /></el-icon>
        保存
      </el-button>
      <el-button size="small" type="success" @click="openRunDialog">
        <el-icon class="mr-1"><VideoPlay /></el-icon>
        试运行
      </el-button>
    </header>

    <div class="flex-1 flex min-h-0">
      <!-- 左: 节点面板 -->
      <NodePalette @add="addNodeAtCenter" />

      <!-- 中: Vue Flow 画布 -->
      <div ref="canvasRef" class="flex-1 min-w-0 relative" @dragover.prevent @drop="onDrop">
        <VueFlow
          class="h-full w-full"
          :fit-view-on-init="true"
          :delete-key-code="['Backspace', 'Delete']"
          :default-edge-options="defaultEdgeOptions"
          @node-click="onNodeClick"
          @pane-click="selectedNodeId = ''"
          @connect="onConnect"
        >
          <!-- 五类节点共用渲染组件(按业务 type 区分外观) -->
          <template v-for="t in nodeTypes" #[`node-${t}`]="nodeProps" :key="t">
            <AgentFlowNode v-bind="nodeProps" />
          </template>
          <Background :gap="18" />
          <Controls />
          <MiniMap pannable zoomable />
        </VueFlow>

        <!-- 画布空提示 -->
        <div
          v-if="nodes.length === 0"
          class="absolute inset-0 flex-center pointer-events-none text-note-sub"
        >
          <p class="text-sm m-0">从左侧拖入节点开始编排工作流</p>
        </div>
      </div>

      <!-- 右: 属性面板 -->
      <NodeConfigPanel
        :node="selectedConfigNode"
        :upstreams="upstreamsOfSelected"
        :model-list="models"
        @remove="removeNode"
      />
    </div>

    <!-- 试运行对话框 -->
    <el-dialog v-model="runDialogVisible" title="工作流试运行" width="640px">
      <div class="flex flex-col gap-3">
        <LLMSelect v-model:model-id="modelId" :model-list="models" size="small" />
        <div>
          <div class="flex items-center justify-between mb-1">
            <span class="text-sm font-medium text-note">输入</span>
            <span v-if="agent?.input_type === 'json'" class="text-xs text-note-sub">JSON 格式</span>
          </div>
          <el-input v-model="runInputText" type="textarea" :rows="4" :placeholder="runPlaceholder" />
        </div>

        <!-- 运行结果 -->
        <template v-if="runResult !== null">
          <div>
            <span class="text-sm font-medium text-note">结果</span>
            <pre class="text-xs whitespace-pre-wrap m-0 text-note bg-note-soft rounded-lg p-2.5 mt-1 overflow-x-auto">{{ runResultText }}</pre>
          </div>
          <!-- 节点执行轨迹 -->
          <div v-if="runTrace.length">
            <span class="text-sm font-medium text-note">节点轨迹</span>
            <div class="mt-1 flex flex-col gap-1">
              <div
                v-for="t in runTrace" :key="t.node_id"
                class="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-note-soft/70 text-xs"
              >
                <span
                  class="w-2 h-2 rounded-full shrink-0"
                  :class="t.status === 'success' ? 'bg-green-500' : t.status === 'failed' ? 'bg-red-500' : 'bg-gray-300'"
                />
                <span class="font-medium text-note">{{ nodeLabel(t.node_type) }}</span>
                <span class="text-note-sub font-mono">{{ t.node_id }}</span>
                <span class="text-note-sub">{{ t.duration_ms }}ms</span>
                <span class="flex-1" />
                <el-popover trigger="click" width="320">
                  <template #reference>
                    <button type="button" class="text-note-sub hover:text-note-green transition-colors">
                      查看输出
                    </button>
                  </template>
                  <pre class="text-xs whitespace-pre-wrap m-0 max-h-60 overflow-auto">{{ traceDetail(t) }}</pre>
                </el-popover>
              </div>
            </div>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="runDialogVisible = false">关闭</el-button>
        <el-button type="success" :loading="runLoading" :disabled="!runInputText.trim()" @click="handleRun">
          运行
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
// 工作流可视化编辑器: Vue Flow 画布编排 + 保存到智能体 + 试运行
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'
import { Back, Finished, VideoPlay } from '@element-plus/icons-vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import type { Connection } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import { ElMessage } from 'element-plus'
import NodePalette from '../../components/workflow/NodePalette.vue'
import AgentFlowNode from '../../components/workflow/AgentFlowNode.vue'
import NodeConfigPanel from '../../components/workflow/NodeConfigPanel.vue'
import LLMSelect from '../../../ai/components/LLMSelect.vue'
import { NODE_TYPE_META } from '../../components/workflow/meta'
import { getAgent, saveAgentWorkflow, runAgent } from '../../api/agent'
import { listModelConfigs } from '../../../ai/api/model_config'
import type { PaginationParams, PaginationResponse } from '@/common/types/common'
import type { ModelConfig } from '../../../ai/types/model_config'
import type {
  Agent, NodeTrace, WorkflowGraph, WorkflowNode, WorkflowNodeType,
} from '../../types'

const route = useRoute()
const agentId = computed(() => String((route.params as { id?: string }).id ?? ''))

// 五类节点类型(模板插槽动态注册: #node-start / #node-llm / ...)
const nodeTypes = Object.keys(NODE_TYPE_META) as WorkflowNodeType[]

// ===== 画布实例(官方模式: store 的 nodes/edges 响应式数组直接读写) =====
const { nodes, edges, addNodes, addEdges, setNodes, setEdges, screenToFlowCoordinate } = useVueFlow()

// 连线默认样式(便签绿 + 流动虚线)
const defaultEdgeOptions = { animated: true, style: { stroke: '#7fb69a', strokeWidth: 2 } }

// ===== 智能体与画布数据 =====
const agent = ref<Agent | null>(null)
const saving = ref(false)

// 各类型节点的默认配置(新增节点时填充)
const defaultData = (type: WorkflowNodeType): WorkflowNode['data'] => {
  if (type === 'llm') return { prompt: '', model_id: null, output_type: 'str', output_schema: null }
  if (type === 'condition') return { left_source: '', left_path: '', operator: 'eq', right: '' }
  if (type === 'template') return { template: '' }
  if (type === 'end') return { result: '' }
  return {}
}

// 生成不冲突的节点ID(n1, n2, ...)
const nextNodeId = () => {
  let max = 0
  for (const n of nodes.value) {
    const m = /^n(\d+)$/.exec(n.id)
    if (m) max = Math.max(max, Number(m[1]))
  }
  return `n${max + 1}`
}

// 初始图: 已配置则读回, 否则种子 开始→结束
const initGraph = (graph: WorkflowGraph | null) => {
  if (graph && graph.nodes.length > 0) {
    setNodes(graph.nodes.map((n) => ({
      id: n.id,
      type: n.type,
      position: { ...n.position },
      data: { ...defaultData(n.type), ...n.data },
    })))
    setEdges(graph.edges.map((e) => ({
      id: e.id, source: e.source, target: e.target, sourceHandle: e.sourceHandle ?? null,
    })))
  } else {
    setNodes([
      { id: 'n1', type: 'start', position: { x: 60, y: 140 }, data: {} },
      { id: 'n2', type: 'end', position: { x: 420, y: 140 }, data: {} },
    ])
    setEdges([{ id: 'e-seed', source: 'n1', target: 'n2', sourceHandle: null }])
  }
}

onMounted(async () => {
  loadModels()
  try {
    agent.value = await getAgent(agentId.value)
    initGraph(agent.value.workflow)
  } catch (error) {
    console.error('加载智能体失败:', error)
    ElMessage.error('智能体不存在或加载失败')
    useRouter().replace('/agent/manage')
  }
})

// ===== 节点增删与选择 =====
const selectedNodeId = ref('')
const canvasRef = ref<HTMLDivElement>()

const selectedConfigNode = computed(() => {
  const n = nodes.value.find((nd) => nd.id === selectedNodeId.value)
  return n
    ? { id: n.id, type: n.type as WorkflowNodeType, data: n.data as WorkflowNode['data'] }
    : null
})

// 选中节点的上游节点(引用插入/条件左值来源)
const upstreamsOfSelected = computed(() => {
  if (!selectedNodeId.value) return []
  const upstreamIds = edges.value.filter((e) => e.target === selectedNodeId.value).map((e) => e.source)
  return upstreamIds
    .map((id) => nodes.value.find((nd) => nd.id === id))
    .filter((n): n is (typeof nodes.value)[number] => Boolean(n))
    .map((n) => ({ id: n.id, label: NODE_TYPE_META[n.type as WorkflowNodeType]?.label ?? n.type }))
})

const onNodeClick = ({ node }: { node: { id: string } }) => {
  selectedNodeId.value = node.id
}

const addNode = (type: WorkflowNodeType, position: { x: number; y: number }) => {
  // 开始/结束节点全局唯一
  if ((type === 'start' || type === 'end') && nodes.value.some((n) => n.type === type)) {
    ElMessage.warning(`${NODE_TYPE_META[type].label}节点只能有一个`)
    return
  }
  const id = nextNodeId()
  addNodes([{ id, type, position, data: defaultData(type) }])
  selectedNodeId.value = id
}

// 面板点击添加: 落在画布中心附近(带随机偏移避免完全重叠)
const addNodeAtCenter = (type: WorkflowNodeType) => {
  const rect = canvasRef.value?.getBoundingClientRect()
  const center = rect
    ? { x: rect.left + rect.width / 2 - 88 + Math.random() * 60, y: rect.top + rect.height / 2 - 50 + Math.random() * 60 }
    : { x: 200, y: 200 }
  addNode(type, screenToFlowCoordinate(center))
}

// 拖拽落点: 读取 dataTransfer 的节点类型
const onDrop = (event: DragEvent) => {
  const type = event.dataTransfer?.getData('application/agent-node-type') as WorkflowNodeType
  if (!type || !NODE_TYPE_META[type]) return
  addNode(type, screenToFlowCoordinate({ x: event.clientX, y: event.clientY }))
}

// 删除节点(连同关联连线)
const removeNode = (nodeId: string) => {
  nodes.value = nodes.value.filter((n) => n.id !== nodeId)
  edges.value = edges.value.filter((e) => e.source !== nodeId && e.target !== nodeId)
  if (selectedNodeId.value === nodeId) selectedNodeId.value = ''
}

// 连线: 写入画布(条件节点的 true/false 锚点经 sourceHandle 保留)
const onConnect = (connection: Connection) => {
  addEdges([connection])
}

// ===== 保存 =====
const toGraph = (): WorkflowGraph => ({
  nodes: nodes.value.map((n) => ({
    id: n.id,
    type: n.type as WorkflowNodeType,
    position: { x: n.position.x, y: n.position.y },
    data: JSON.parse(JSON.stringify(n.data)),
  })),
  edges: edges.value.map((e) => ({
    id: e.id, source: e.source, target: e.target, sourceHandle: e.sourceHandle ?? null,
  })),
})

// 本地预校验(与后端 validate_workflow 关键规则一致, 保存前即时反馈)
const localValidate = (graph: WorkflowGraph): string[] => {
  const errors: string[] = []
  const ids = new Set(graph.nodes.map((n) => n.id))
  const starts = graph.nodes.filter((n) => n.type === 'start').length
  const ends = graph.nodes.filter((n) => n.type === 'end').length
  if (starts !== 1) errors.push(`开始节点必须恰好 1 个(当前 ${starts})`)
  if (ends !== 1) errors.push(`结束节点必须恰好 1 个(当前 ${ends})`)
  if (graph.edges.some((e) => e.source === e.target)) errors.push('存在节点自连线')
  if (graph.edges.some((e) => !ids.has(e.source) || !ids.has(e.target))) errors.push('存在未连接节点的悬空连线')
  for (const n of graph.nodes) {
    if (n.type === 'condition') {
      const outs = graph.edges.filter((e) => e.source === n.id)
      if (!outs.some((e) => e.sourceHandle === 'true') || !outs.some((e) => e.sourceHandle === 'false')) {
        errors.push(`条件节点 ${n.id} 需同时连接「是」「否」分支`)
      }
      if (!n.data.left_source || !ids.has(n.data.left_source)) {
        errors.push(`条件节点 ${n.id} 的左值来源无效`)
      }
    }
    const texts = [n.data.prompt, n.data.template, n.data.result].filter(Boolean) as string[]
    for (const text of texts) {
      for (const m of text.matchAll(/\{\{\s*([a-zA-Z0-9_\-]+)/g)) {
        if (!ids.has(m[1])) errors.push(`节点 ${n.id} 引用了不存在的节点: ${m[1]}`)
      }
    }
  }
  return errors
}

const handleSave = async () => {
  const graph = toGraph()
  const errors = localValidate(graph)
  if (errors.length > 0) {
    ElMessage.error(errors.slice(0, 2).join('；'))
    return
  }
  saving.value = true
  try {
    await saveAgentWorkflow(agentId.value, { agent_type: 'workflow', workflow: graph })
    ElMessage.success('工作流已保存')
    if (agent.value) {
      agent.value = { ...agent.value, agent_type: 'workflow', workflow: graph }
    }
  } catch (error) {
    console.error('保存工作流失败:', error)
  } finally {
    saving.value = false
  }
}

// ===== 试运行 =====
const models = ref<ModelConfig[]>([])
const modelId = ref('')
const runDialogVisible = ref(false)
const runInputText = ref('')
const runLoading = ref(false)
const runResult = ref<unknown>(null)
const runTrace = ref<NodeTrace[]>([])

const loadModels = async () => {
  try {
    const params = { page: 1, size: 50, model_type: 'chat' } as PaginationParams
    const res: PaginationResponse<ModelConfig> = await listModelConfigs(params)
    models.value = res.items
    if (res.items.length > 0) modelId.value = res.items[0].id
  } catch (error) {
    console.error('加载模型列表失败:', error)
  }
}

const runPlaceholder = computed(() =>
  agent.value?.input_type === 'json'
    ? '{"key": "value"}'
    : '输入开始节点的数据',
)

const openRunDialog = () => {
  runResult.value = null
  runTrace.value = []
  runDialogVisible.value = true
}

const runResultText = computed(() =>
  typeof runResult.value === 'string' ? runResult.value : JSON.stringify(runResult.value, null, 2),
)

const handleRun = async () => {
  if (runLoading.value || !runInputText.value.trim()) return
  let input: unknown = runInputText.value
  if (agent.value?.input_type === 'json') {
    try {
      input = JSON.parse(runInputText.value)
    } catch {
      ElMessage.warning('输入 JSON 格式不正确')
      return
    }
  }
  runLoading.value = true
  try {
    const res = await runAgent(agentId.value, { model_id: modelId.value, input })
    runResult.value = res.result
    runTrace.value = res.trace ?? []
  } catch (error) {
    console.error('工作流试运行失败:', error)
  } finally {
    runLoading.value = false
  }
}

// ===== 轨迹展示辅助 =====
const nodeLabel = (type: string) => NODE_TYPE_META[type as WorkflowNodeType]?.label ?? type

const traceDetail = (t: NodeTrace) => {
  const parts = [`状态: ${t.status}`]
  if (t.error) parts.push(`错误: ${t.error}`)
  parts.push(`输出: ${typeof t.output === 'string' ? t.output : JSON.stringify(t.output, null, 2)}`)
  return parts.join('\n')
}
</script>

<style>
/* Vue Flow 画布融入便签风主题 */
.vue-flow__node {
  font-family: inherit;
}
.vue-flow__minimap,
.vue-flow__controls {
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid rgba(127, 182, 154, 0.35);
}
.vue-flow__controls-button {
  border-bottom: none;
}
.vue-flow__handle {
  border: none;
}
</style>
