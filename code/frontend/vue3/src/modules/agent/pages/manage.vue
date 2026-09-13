<template>
  <div p-4 md:p-6 w-full>
    <!-- 顶部: 页面导航 + 新建 -->
    <div mb-4 flex flex-wrap items-center gap-2>
      <RouterLink
        to="/agent/chat"
        flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-note-tint text-sm text-note
        hover:text-note-green hover:shadow-note transition-all
      >
        <el-icon :size="14"><ChatDotRound /></el-icon>
        智能体对话
      </RouterLink>
      <span flex-1 />
      <button
        class="active:scale-[0.98]"
        flex items-center gap-1.5 px-4 py-2 rounded-xl bg-note-green text-white text-sm font-medium
        shadow-note hover:opacity-90 transition-all
        @click="handleCreate"
      >
        <el-icon :size="16"><Plus /></el-icon>
        新建智能体
      </button>
    </div>

    <!-- 范围切换: 全部 / 内置公共 / 我的 -->
    <el-radio-group v-model="scopeFilter" mb-3>
      <el-radio-button value="all">全部</el-radio-button>
      <el-radio-button value="builtin">内置公共</el-radio-button>
      <el-radio-button value="mine">我的</el-radio-button>
    </el-radio-group>

    <!-- 智能体卡片网格(便签风) -->
    <div v-loading="loading" grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3>
      <div
        v-for="agent in filteredAgents" :key="agent.id"
        flex flex-col gap-3 p-4 rounded-2xl bg-note-card shadow-note
        hover:shadow-note-hover hover:-translate-y-0.5 transition-all
      >
        <!-- 头部: 图标 + 名称 + 标签 -->
        <div flex items-center gap-2.5>
          <div
            w-10 h-10 rounded-xl flex-center shrink-0
            :class="agent.agent_type === 'workflow' ? 'bg-sky-500/10' : 'bg-note-tint'"
          >
            <el-icon :size="20" :class="agent.agent_type === 'workflow' ? 'text-sky-600' : 'text-note-green'">
              <Share v-if="agent.agent_type === 'workflow'" />
              <MagicStick v-else />
            </el-icon>
          </div>
          <div min-w-0 flex-1>
            <div font-medium text-note truncate>{{ agent.name }}</div>
            <div text-xs text-note-sub mt-0.5>{{ formatDate(agent.updated_at) }} 更新</div>
          </div>
          <el-tag v-if="agent.agent_type === 'workflow'" size="small" effect="plain" type="primary">
            工作流
          </el-tag>
        </div>
        <!-- 描述 -->
        <p text-sm text-note-sub leading-relaxed line-clamp-2 min-h-10 m-0>
          {{ agent.description || '暂无描述' }}
        </p>
        <!-- 提示词预览 -->
        <p
          class="text-note-sub/80 bg-note-soft/70 border-note/60"
          text-xs leading-relaxed line-clamp-3 rounded-lg p-2.5 m-0 border
        >
          {{ agent.system_prompt }}
        </p>
        <!-- 底部: 归属标签 + 操作 -->
        <div flex items-center justify-between pt-2.5 border-t border-note>
          <el-tag size="small" effect="plain" :type="agent.is_builtin ? 'success' : agent.is_public ? 'warning' : 'info'">
            {{ agent.is_builtin ? '内置公共' : agent.is_public ? '公共' : '我的' }}
          </el-tag>
          <div v-if="isMine(agent)" flex items-center gap-1>
            <el-button size="small" text bg :type="agent.agent_type === 'workflow' ? 'primary' : 'default'" @click="goWorkflow(agent)">
              <el-icon class="mr-0.5"><Share /></el-icon>
              {{ agent.agent_type === 'workflow' ? '编辑工作流' : '配置工作流' }}
            </el-button>
            <el-button size="small" text bg type="primary" @click="handleEdit(agent)">编辑</el-button>
            <el-button size="small" text bg type="danger" :disabled="agent.is_builtin" @click="handleDelete(agent)">
              删除
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!loading && filteredAgents.length === 0" py-16 flex flex-col items-center text-note-sub>
      <el-icon text-5xl mb-3 class="opacity-40"><MagicStick /></el-icon>
      <p m-0>{{ scopeFilter === 'mine' ? '还没有自己的智能体，点击右上角"新建智能体"开始' : '暂无智能体' }}</p>
    </div>

    <!-- 分页(手机居中, 桌面靠右) -->
    <div mt-4 flex flex-wrap justify-center sm:justify-end>
      <el-pagination
        v-model:current-page="pagination.page" v-model:page-size="pagination.size"
        :total="total" layout="total, prev, pager, next"
        @current-change="fetchData"
      />
    </div>

    <!-- 新建/编辑智能体对话框(基础配置 + 可选结构体配置) -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑智能体' : '新建智能体'" width="90%" class="max-w-[720px]">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="90px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如: 产品文案助手" maxlength="100" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" placeholder="一句话说明智能体用途" maxlength="200" />
        </el-form-item>
        <el-form-item label="系统提示词" prop="system_prompt">
          <el-input
            v-model="form.system_prompt" type="textarea" :rows="6" maxlength="4000" show-word-limit
            placeholder="定义智能体的角色、能力与行为规则，如：你是一位数据清洗专家，擅长…"
          />
        </el-form-item>

        <!-- 智能体类型: 简单(单轮对话/运行) 或 工作流(Vue Flow 节点编排) -->
        <el-form-item label="智能体类型">
          <div class="w-full">
            <el-radio-group v-model="form.agent_type">
              <el-radio value="simple" border>简单智能体</el-radio>
              <el-radio value="workflow" border>工作流智能体</el-radio>
            </el-radio-group>
            <p class="text-xs text-note-sub m-0 mt-1.5 leading-relaxed">
              {{ form.agent_type === 'workflow'
                ? '创建后在卡片上点击「编辑工作流」，用可视化画布编排 LLM / 条件 / 模板节点'
                : '单次提示词驱动，适合对话与简单任务' }}
            </p>
          </div>
        </el-form-item>

        <!-- 结构体配置(可选, 默认字符串输入/输出) -->
        <el-divider class="my-2">
          <span class="text-xs text-note-sub font-normal">结构体配置(可选, 默认字符串输入 / 字符串输出)</span>
        </el-divider>
        <el-form-item label="输入类型">
          <el-radio-group v-model="form.input_type">
            <el-radio value="str" border>字符串</el-radio>
            <el-radio value="json" border>JSON 结构体</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.input_type === 'json'" label="输入结构">
          <div class="w-full">
            <TreeSchemaEditor v-model="form.input_schema" />
          </div>
        </el-form-item>
        <el-form-item label="输出类型">
          <el-radio-group v-model="form.output_type">
            <el-radio value="str" border>字符串</el-radio>
            <el-radio value="json" border>JSON 结构体</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.output_type === 'json'" label="输出结构">
          <div class="w-full">
            <TreeSchemaEditor v-model="form.output_schema" />
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">
            {{ editingId ? '保存' : '创建' }}
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Plus, MagicStick, ChatDotRound, Share } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { useAuthStore } from '@/common/stores/auth'
import type { PaginationParams } from '@/common/types/common'
import TreeSchemaEditor from '../components/TreeSchemaEditor.vue'
import {
  listAgents,
  createAgent,
  updateAgent,
  deleteAgent,
} from '../api/agent'
import type { Agent, AgentIOType, AgentType } from '../types'

const authStore = useAuthStore()
const router = useRouter()
const currentUserId = computed(() => authStore.authState.user.id)

// ==================== 列表 ====================

const pagination = ref<PaginationParams>({ page: 1, size: 24 })
const total = ref(0)
const loading = ref(false)
const agents = ref<Agent[]>([])

// 范围过滤(前端过滤: 全部/内置公共/我的)
const scopeFilter = ref<'all' | 'builtin' | 'mine'>('all')
const filteredAgents = computed(() => {
  if (scopeFilter.value === 'builtin') return agents.value.filter((a) => a.is_public && a.is_builtin)
  if (scopeFilter.value === 'mine') return agents.value.filter((a) => isMine(a))
  return agents.value
})

// 是否本人创建(可编辑; 内置公共由种子维护, 不提供编辑入口)
const isMine = (agent: Agent) => !!agent.created_by && agent.created_by === currentUserId.value

const formatDate = (value: string) => new Date(value).toLocaleDateString()

// 获取智能体列表
const fetchData = async () => {
  try {
    loading.value = true
    const res = await listAgents(pagination.value)
    agents.value = res.items
    total.value = res.total
  } catch (error) {
    console.error('获取智能体列表失败:', error)
    ElMessage.error('获取智能体列表失败')
  } finally {
    loading.value = false
  }
}

// ==================== 新建/编辑(基础配置 + 可选结构体配置) ====================

const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref<string | null>(null)
const formRef = ref<FormInstance>()

// 表单基础值(结构体不配置 = 默认字符串输入/输出)
const formBase = {
  name: '',
  description: '',
  system_prompt: '',
  agent_type: 'simple' as AgentType,
  input_type: 'str' as AgentIOType,
  output_type: 'str' as AgentIOType,
  input_schema: null as Record<string, unknown> | null,
  output_schema: null as Record<string, unknown> | null,
}
const form = reactive({ ...formBase })

const rules = {
  name: [{ required: true, message: '请输入智能体名称', trigger: 'blur' }],
  system_prompt: [{ required: true, message: '请输入系统提示词', trigger: 'blur' }],
}

const handleCreate = () => {
  editingId.value = null
  Object.assign(form, formBase)
  dialogVisible.value = true
}

const handleEdit = (agent: Agent) => {
  editingId.value = agent.id
  Object.assign(form, {
    name: agent.name,
    description: agent.description,
    system_prompt: agent.system_prompt,
    agent_type: agent.agent_type ?? 'simple',
    input_type: agent.input_type ?? 'str',
    output_type: agent.output_type ?? 'str',
    input_schema: agent.input_schema ?? null,
    output_schema: agent.output_schema ?? null,
  })
  dialogVisible.value = true
}

// 跳转工作流可视化编辑器(保存时会把类型切换为 workflow)
const goWorkflow = (agent: Agent) => {
  router.push(`/agent/workflow/${agent.id}`)
}

const handleSubmit = async () => {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    submitting.value = true
    // 字符串类型不携带结构(schema 置空, 避免遗留脏配置)
    const payload = {
      ...form,
      input_schema: form.input_type === 'json' ? form.input_schema : null,
      output_schema: form.output_type === 'json' ? form.output_schema : null,
    }
    if (editingId.value) {
      await updateAgent(editingId.value, payload)
      ElMessage.success('智能体已更新')
    } else {
      await createAgent(payload)
      ElMessage.success('智能体已创建')
    }
    dialogVisible.value = false
    fetchData()
  } catch (error) {
    console.error('保存智能体失败:', error)
    ElMessage.error('保存失败')
  } finally {
    submitting.value = false
  }
}

// 删除智能体
const handleDelete = async (agent: Agent) => {
  try {
    await ElMessageBox.confirm(
      `确定删除智能体"${agent.name}"吗？关联对话不会受影响。`,
      '删除智能体',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await deleteAgent(agent.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (error) {
    console.log('取消删除或删除失败:', error)
  }
}

onMounted(() => {
  fetchData()
})
</script>
