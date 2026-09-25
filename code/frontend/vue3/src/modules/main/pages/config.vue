<template>
  <div p-4 md:p-6>
    <InkPageHead
      title="通用配置"
      sub="令牌 / 邮箱 / 网页搜索 / 文件存储 / 数据库 / 任务队列等平台级动态配置"
      seal="配"
    >
      <template #actions>
        <el-button :icon="Refresh" plain @click="load">刷新</el-button>
      </template>
    </InkPageHead>

    <div class="flex gap-4 h-full">
      <!-- 左侧: 配置组列表 -->
      <el-aside width="220px" class="bg-note-card border border-note rounded-xl shadow-note overflow-hidden">
        <el-menu :default-active="activeGroup" class="border-r-0" @select="(i: string) => (activeGroup = i)">
          <el-menu-item v-for="g in groups" :key="g.group" :index="g.group">
            <span>{{ g.name }}</span>
            <el-tag v-if="g.restart_required" size="small" type="warning" class="ml-auto">重启</el-tag>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <!-- 右侧: 组表单(由后端字段元数据驱动, 新增配置组前端零改动) -->
      <el-main class="bg-note-card border border-note rounded-xl shadow-note overflow-auto">
        <template v-if="current">
          <div class="mb-4">
            <h2 class="text-lg font-bold text-note">{{ current.name }}</h2>
            <p class="text-sm text-note-sub mt-1">{{ current.description }}</p>
            <el-alert
              v-if="current.restart_required"
              type="warning" :closable="false" show-icon class="mt-2"
              title="本组含连接级配置, 修改保存后需重启后端服务才能生效"
            />
            <p v-if="current.updated_at" class="text-xs text-note-sub mt-2">
              最近更新: {{ current.updated_at.replace('T', ' ').slice(0, 19) }}
              <template v-if="current.updated_by"> · {{ current.updated_by }}</template>
            </p>
          </div>
          <el-form label-width="180px" label-position="left">
            <el-form-item v-for="f in current.fields" :key="f.key" :label="f.title">
              <div class="w-full">
                <!-- 密钥: 留空保持不变; 输入空格+保存=清除 -->
                <el-input
                  v-if="f.type === 'secret'" v-model="form[f.key]" type="password" show-password
                  :placeholder="f.has_value ? '已配置 · 留空保持不变 · 输入一个空格保存即清除' : '未配置'"
                />
                <!-- 布尔 -->
                <el-switch v-else-if="f.type === 'bool'" v-model="form[f.key]" />
                <!-- 数字 -->
                <el-input-number
                  v-else-if="f.type === 'int' || f.type === 'float'"
                  v-model="form[f.key]" :step="f.type === 'float' ? 0.5 : 1"
                  class="!w-52"
                />
                <!-- 枚举 -->
                <el-select v-else-if="f.type === 'enum'" v-model="form[f.key]" class="!w-72">
                  <el-option v-for="o in f.options" :key="o" :label="o" :value="o" />
                </el-select>
                <!-- 列表(tags 输入) -->
                <el-select
                  v-else-if="f.type === 'list'" v-model="form[f.key]" multiple filterable allow-create
                  default-first-option class="!w-full" placeholder="输入后回车添加"
                />
                <!-- 文本 -->
                <el-input v-else v-model="form[f.key]" />
                <div v-if="f.description" class="text-xs text-note-sub mt-1">{{ f.description }}</div>
              </div>
            </el-form-item>
          </el-form>
          <div class="flex justify-end gap-2 mt-2">
            <el-button @click="resetForm">放弃修改</el-button>
            <el-button type="primary" :loading="saving" @click="save">保存配置</el-button>
          </div>
        </template>
      </el-main>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 系统通用配置页(管理员): 表单由后端字段元数据驱动, 新增配置组前端零改动
 * 左侧组列表 + 右侧表单; 密钥字段留空提交=保持不变
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { listSysConfigs, updateSysConfig } from '../api/sys_config';
import type { ConfigGroup } from '../api/sys_config';

const groups = ref<ConfigGroup[]>([])
const activeGroup = ref('')
const saving = ref(false)
const form = reactive<Record<string, unknown>>({})

const current = computed(() => groups.value.find(g => g.group === activeGroup.value))

/** 字段值载入表单(密钥字段留空, 不回显明文) */
function resetForm() {
  if (!current.value) return
  for (const f of current.value.fields) {
    form[f.key] = f.type === 'secret' ? '' : (f.value as unknown)
  }
}

/** 表单打平的 key("tavily.api_key") → 嵌套结构提交 */
function buildPayload(): Record<string, unknown> {
  const payload: Record<string, unknown> = {}
  for (const f of current.value?.fields ?? []) {
    const v = form[f.key]
    if (f.type === 'secret' && v === '') continue // 密钥留空=保持不变
    const parts = f.key.split('.')
    let cur = payload
    for (let i = 0; i < parts.length - 1; i++) {
      cur[parts[i]] = (cur[parts[i]] as Record<string, unknown>) ?? {}
      cur = cur[parts[i]] as Record<string, unknown>
    }
    cur[parts[parts.length - 1]] = v
  }
  return payload
}

/** 拉取全部配置组(保存/刷新共用) */
async function load() {
  const { groups: gs } = await listSysConfigs()
  groups.value = gs
  if (!activeGroup.value) activeGroup.value = gs[0]?.group ?? ''
  resetForm()
}

async function save() {
  if (!current.value) return
  saving.value = true
  try {
    await updateSysConfig(current.value.group, buildPayload())
    ElMessage.success(`${current.value.name} 已保存${current.value.restart_required ? '(重启后生效)' : ''}`)
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
// 切组时重载表单
watch(activeGroup, resetForm)
</script>

<style scoped>
:deep(.el-aside) { flex-shrink: 0; }
</style>
