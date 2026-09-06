<template>
  <div w-full>
    <!-- 工具条: 关键字搜索 + 新增绑定 -->
    <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
      <el-input v-model="keyword" placeholder="搜索用户/角色/域" clearable class="max-w-[260px]" :prefix-icon="Search" />
      <el-button type="primary" :icon="Plus" @click="openAdd">新增绑定</el-button>
    </div>

    <!-- 用户角色绑定卡片(按用户分组, 每行一条绑定: 域 + 角色) -->
    <div v-loading="loading" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
      <el-card v-for="c in filteredCards" :key="c.user.id" shadow="never" class="!border-note">
        <template #header>
          <div class="flex items-center gap-2">
            <el-avatar :size="28" :icon="UserFilled" />
            <div class="min-w-0">
              <div class="text-sm text-note truncate">{{ c.user.nickname || c.user.username }}</div>
              <div class="text-xs text-note-sub truncate">{{ c.user.username }}</div>
            </div>
            <el-tag size="small" type="info" class="ml-auto shrink-0">{{ c.bindings.length }} 个角色</el-tag>
          </div>
        </template>
        <div class="flex flex-col gap-2">
          <div v-for="b in c.bindings" :key="b.dom + ':' + b.role_key"
            class="flex items-center justify-between gap-2 border border-note rounded px-2 py-1.5">
            <div class="flex items-center gap-1 flex-wrap">
              <el-tag size="small" :type="b.dom === '*' ? 'danger' : 'primary'">{{ domLabel(b.dom) }}</el-tag>
              <el-tag size="small" type="warning">{{ roleLabel(b.role_key) }}</el-tag>
            </div>
            <el-button size="small" type="danger" link :icon="Close" @click="handleRemove(b)" />
          </div>
        </div>
      </el-card>
    </div>
    <el-empty v-if="!loading && !filteredCards.length" description="暂无用户角色绑定" />

    <!-- 新增绑定对话框 -->
    <el-dialog v-model="addVisible" title="新增用户角色绑定" width="90%" class="max-w-[480px]">
      <el-form :model="addForm" :rules="addRules" ref="addFormRef" label-width="72px">
        <el-form-item label="用户" prop="user_id">
          <el-select v-model="addForm.user_id" filterable placeholder="搜索并选择用户" w-full>
            <el-option v-for="u in userOptions" :key="u.id" :label="`${u.nickname || u.username} (${u.username})`"
              :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="角色" prop="role_key">
          <el-select v-model="addForm.role_key" filterable placeholder="选择角色" w-full>
            <el-option v-for="r in roleOptions" :key="r.role_key" :label="roleLabel(r.role_key)" :value="r.role_key" />
          </el-select>
        </el-form-item>
        <el-form-item label="域" prop="dom">
          <el-select v-model="addForm.dom" filterable placeholder="选择域(全局或模块)" w-full>
            <el-option v-for="opt in domOptions" :key="opt" :label="domLabel(opt)" :value="opt" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="addVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="handleAdd">确认</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Search, Plus, Close, UserFilled } from '@element-plus/icons-vue'
import { getAllGroupingPolicies, addRoleForUser, removeRoleForUser, getModuleTree, type GroupingPolicyRow } from '../api/casbin'
import { listRoles } from '../api/role'
import { listUsers } from '../api/user'
import type { PaginationResponse } from '@/common/types/common'
import type { User } from '../types/user'
import type { Role } from '../types/role'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'

// ---------------- 数据 ----------------
const loading = ref(false)
const submitting = ref(false)
const keyword = ref('')
const groupings = ref<GroupingPolicyRow[]>([])
const userOptions = ref<User[]>([])
const roleOptions = ref<Role[]>([])
const moduleCodes = ref<{ code: string; name: string }[]>([])

// 域候选: 全局 + 各模块声明域
const domOptions = computed(() => ['*', ...moduleCodes.value.map((m) => m.code)])

const userMap = computed(() => new Map(userOptions.value.map((u) => [u.id, u])))

const roleLabel = (key: string) => {
  const r = roleOptions.value.find((o) => o.role_key === key)
  return r?.name ? `${r.name}(${key})` : key
}
const domLabel = (dom: string) => {
  if (dom === '*') return '全局(*)'
  const m = moduleCodes.value.find((x) => x.code === dom)
  return m ? `${m.name}(${dom})` : dom
}

// 按用户聚合绑定(仅展示存在绑定的用户)
const cards = computed(() => {
  const byUser = new Map<string, GroupingPolicyRow[]>()
  for (const g of groupings.value) {
    if (!byUser.has(g.user_id)) byUser.set(g.user_id, [])
    byUser.get(g.user_id)!.push(g)
  }
  return [...byUser.entries()]
    .map(([uid, bindings]) => ({
      user: userMap.value.get(uid) || ({ id: uid, username: uid, nickname: '' } as User),
      bindings,
    }))
    .sort((a, b) => a.user.username.localeCompare(b.user.username))
})

// 关键字过滤(用户名/昵称/角色/域)
const filteredCards = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return cards.value
  return cards.value.filter(
    (c) =>
      c.user.username.toLowerCase().includes(q) ||
      (c.user.nickname || '').toLowerCase().includes(q) ||
      c.bindings.some((b) => b.role_key.toLowerCase().includes(q) || b.dom.toLowerCase().includes(q))
  )
})

// ---------------- 新增/移除绑定 ----------------
const addVisible = ref(false)
const addFormRef = ref<FormInstance>()
const addForm = reactive({ user_id: '', role_key: '', dom: '*' })
const addRules = {
  user_id: [{ required: true, message: '请选择用户', trigger: 'change' }],
  role_key: [{ required: true, message: '请选择角色', trigger: 'change' }],
  dom: [{ required: true, message: '请选择域', trigger: 'change' }],
}

const openAdd = () => {
  Object.assign(addForm, { user_id: '', role_key: '', dom: '*' })
  addVisible.value = true
}

const handleAdd = async () => {
  if (!addFormRef.value) return
  const valid = await addFormRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    submitting.value = true
    await addRoleForUser({ ...addForm })
    ElMessage.success('角色绑定成功')
    addVisible.value = false
    await refresh()
  } catch (error) {
    console.error('绑定失败:', error)
    ElMessage.error('绑定失败(用户可能已拥有该角色)')
  } finally {
    submitting.value = false
  }
}

const handleRemove = async (row: GroupingPolicyRow) => {
  const u = userMap.value.get(row.user_id)
  try {
    await ElMessageBox.confirm(
      `确定移除用户 "${u ? u.nickname || u.username : row.user_id}" 在${domLabel(row.dom)}域的角色 "${roleLabel(row.role_key)}" 吗？`,
      '警告',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    await removeRoleForUser({ user_id: row.user_id, role_key: row.role_key, dom: row.dom })
    ElMessage.success('角色绑定已移除')
    await refresh()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    console.error('移除绑定失败:', error)
  }
}

// ---------------- 数据加载 ----------------
const refresh = async () => {
  try {
    loading.value = true
    const [gRes, rRes, uRes, tRes] = await Promise.all([
      getAllGroupingPolicies(),
      listRoles({ page: 1, size: 200 }),
      listUsers({ page: 1, size: 500 }),
      getModuleTree(),
    ])
    groupings.value = gRes.data
    roleOptions.value = (rRes as PaginationResponse<Role>).items || []
    userOptions.value = uRes.items
    moduleCodes.value = tRes.data.map((m) => ({ code: m.code, name: m.name }))
  } catch (error) {
    console.error('获取绑定数据失败:', error)
    ElMessage.error('获取绑定数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(refresh)
</script>
