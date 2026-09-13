<template>
  <!-- 右侧节点属性面板(按选中节点类型渲染配置表单) -->
  <div class="w-72 shrink-0 border-l border-note bg-note-card/60 flex flex-col overflow-y-auto">
    <!-- 未选中提示 -->
    <template v-if="!node">
      <div class="flex-1 flex flex-col items-center justify-center text-note-sub py-10 px-4">
        <el-icon text-4xl mb-2 class="opacity-40"><Setting /></el-icon>
        <p class="text-xs m-0 text-center">选中画布中的节点编辑属性</p>
      </div>
    </template>

    <template v-else>
      <!-- 头部: 节点类型 + 删除 -->
      <div class="flex items-center gap-2 px-3 py-2.5 border-b border-note">
        <div class="w-7 h-7 rounded-lg flex-center shrink-0" :class="meta.tintClass">
          <el-icon :size="14" :class="meta.iconClass"><component :is="meta.icon" /></el-icon>
        </div>
        <span class="text-sm font-bold text-note">{{ meta.label }}节点</span>
        <span class="text-[11px] text-note-sub font-mono">{{ node.id }}</span>
        <span class="flex-1" />
        <el-button
          v-if="node.type !== 'start'" size="small" text bg type="danger"
          @click="$emit('remove', node.id)"
        >
          删除
        </el-button>
      </div>

      <div class="p-3 flex flex-col gap-3">
        <!-- ===== 开始节点: 仅说明 ===== -->
        <template v-if="node.type === 'start'">
          <p class="text-xs text-note-sub m-0 leading-relaxed">
            运行时, 用户输入(字符串或 JSON)作为本节点的输出, 供下游节点通过
            <code class="bg-note-soft px-1 rounded">{{ '{' }}{{ node.id }}{{ '}' }}</code> 引用。
          </p>
        </template>

        <!-- ===== LLM 节点 ===== -->
        <template v-else-if="node.type === 'llm'">
          <div>
            <div class="text-xs font-medium text-note mb-1">模型(空则用运行时选择的模型)</div>
            <LLMSelect
              :model-id="node.data.model_id ?? undefined"
              :model-list="modelList"
              size="small"
              @update:model-id="node.data.model_id = $event"
            />
          </div>
          <div>
            <div class="text-xs font-medium text-note mb-1">提示词</div>
            <el-input
              v-model="node.data.prompt" type="textarea" :rows="5" maxlength="4000"
              placeholder="支持引用上游输出: {{节点ID.字段}}"
            />
            <RefChips v-if="upstreams.length" :upstreams="upstreams" @insert="appendRef(node.data, 'prompt', $event)" />
          </div>
          <div>
            <div class="text-xs font-medium text-note mb-1">输出类型</div>
            <el-radio-group v-model="node.data.output_type" size="small">
              <el-radio-button value="str">字符串</el-radio-button>
              <el-radio-button value="json">JSON 结构体</el-radio-button>
            </el-radio-group>
          </div>
          <div v-if="node.data.output_type === 'json'">
            <div class="text-xs font-medium text-note mb-1">输出结构(可选)</div>
            <TreeSchemaEditor
              :model-value="node.data.output_schema ?? null"
              @update:model-value="node.data.output_schema = $event"
            />
          </div>
        </template>

        <!-- ===== 条件节点 ===== -->
        <template v-else-if="node.type === 'condition'">
          <div>
            <div class="text-xs font-medium text-note mb-1">左值来源节点</div>
            <el-select v-model="node.data.left_source" placeholder="选择上游节点" w-full size="small">
              <el-option v-for="u in upstreams" :key="u.id" :value="u.id" :label="`${u.id}(${u.label})`" />
            </el-select>
          </div>
          <div>
            <div class="text-xs font-medium text-note mb-1">左值字段路径(可空)</div>
            <el-input v-model="node.data.left_path" size="small" placeholder="如 score 或 data.name" />
          </div>
          <div>
            <div class="text-xs font-medium text-note mb-1">运算符</div>
            <el-select v-model="node.data.operator" w-full size="small">
              <el-option v-for="op in CONDITION_OPERATORS" :key="op.value" :value="op.value" :label="op.label" />
            </el-select>
          </div>
          <div v-if="node.data.operator !== 'empty'">
            <div class="text-xs font-medium text-note mb-1">右值</div>
            <el-input v-model="node.data.right" size="small" placeholder="比较的字面量" />
          </div>
          <p class="text-[11px] text-note-sub m-0 leading-relaxed">
            命中走「是」分支(绿色锚点), 否则走「否」分支(红色锚点)。
          </p>
        </template>

        <!-- ===== 模板节点 ===== -->
        <template v-else-if="node.type === 'template'">
          <div>
            <div class="text-xs font-medium text-note mb-1">模板文本</div>
            <el-input
              v-model="node.data.template" type="textarea" :rows="5" maxlength="4000"
              placeholder="引用上游输出: {{节点ID.字段}}"
            />
            <RefChips v-if="upstreams.length" :upstreams="upstreams" @insert="appendRef(node.data, 'template', $event)" />
          </div>
        </template>

        <!-- ===== 结束节点 ===== -->
        <template v-else-if="node.type === 'end'">
          <div>
            <div class="text-xs font-medium text-note mb-1">结果模板(可空)</div>
            <el-input
              v-model="node.data.result" type="textarea" :rows="4" maxlength="2000"
              placeholder="空则取最后执行的 LLM 节点输出"
            />
            <RefChips v-if="upstreams.length" :upstreams="upstreams" @insert="appendRef(node.data, 'result', $event)" />
          </div>
          <p class="text-[11px] text-note-sub m-0 leading-relaxed">
            最终输出按智能体的输出类型(str/json)返回并写入运行历史。
          </p>
        </template>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
// 节点属性面板: 直接修改选中节点的 data(响应式, 画布节点同步更新)
import { computed } from 'vue'
import { Setting } from '@element-plus/icons-vue'
import LLMSelect from '../../../ai/components/LLMSelect.vue'
import TreeSchemaEditor from '../TreeSchemaEditor.vue'
import { NODE_TYPE_META, CONDITION_OPERATORS } from './meta'
import type { ModelConfig } from '../../../ai/types/model_config'
import type { AgentIOType, WorkflowNode, WorkflowNodeType } from '../../types'
import RefChips from './RefChips.vue'

const props = defineProps<{
  /** 当前选中的画布节点(未选中为 null; 仅需 id/type/data, 不含 position) */
  node: { id: string; type: WorkflowNodeType; data: WorkflowNode['data'] } | null
  /** 上游节点列表(引用插入与条件左值来源) */
  upstreams: Array<{ id: string; label: string }>
  /** 模型配置列表(LLM 节点用) */
  modelList: ModelConfig[]
}>()

defineEmits<{
  /** 删除节点 */
  remove: [nodeId: string]
}>()

const meta = computed(() => {
  const type = (props.node?.type ?? 'llm') as WorkflowNodeType
  return NODE_TYPE_META[type] ?? NODE_TYPE_META.llm
})

// 追加引用占位符到指定模板字段末尾
const appendRef = (
  data: WorkflowNode['data'],
  field: 'prompt' | 'template' | 'result',
  refText: string,
) => {
  data[field] = `${(data[field] || '').trimEnd()}${data[field] ? ' ' : ''}${refText}`
}

// LLM 节点默认输出类型(新增节点时保证单选组有值)
if (props.node?.type === 'llm' && !props.node.data.output_type) {
  props.node.data.output_type = 'str' as AgentIOType
}
</script>
