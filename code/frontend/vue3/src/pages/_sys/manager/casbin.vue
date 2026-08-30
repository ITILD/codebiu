<template>
  <div p-4 md:p-6 w-full>
    <!-- 工具栏 -->
    <div mb-4 flex flex-wrap items-center gap-2>
      <div w-full sm:w-48 shrink-0>
        <el-select v-model="domFilter" w-full placeholder="全部域" clearable @change="fetchAll">
          <el-option v-for="opt in domOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </div>
      <el-input class="w-full sm:w-60" v-model="searchQuery" placeholder="搜索角色/用户/资源" clearable />
      <div flex-1 />
      <el-button :icon="Refresh" @click="handleReload" :loading="reloading">重载策略</el-button>
    </div>

    <!-- 策略/绑定 双标签页 -->
    <el-tabs v-model="activeTab">
      <!-- 策略规则 -->
      <el-tab-pane label="策略规则" name="policy">
        <div mb-3 flex justify-end>
          <el-button type="primary" size="small" :icon="Plus" @click="openPolicyDialog">
            新增策略
          </el-button>
        </div>
        <el-table v-loading="policyLoading" :data="filteredPolicies" stripe w-full>
          <el-table-column label="主体(角色)" min-width="140">
            <template #default="{ row }">
              <el-tag size="small" type="warning">{{ row.sub }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="域" min-width="120">
            <template #default="{ row }">
              <el-tag size="small" :type="row.dom === '*' ? 'danger' : 'primary'">{{ domLabel(row.dom) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="obj" label="资源" min-width="120" />
          <el-table-column label="动作" min-width="200">
            <template #default="{ row }">
              <div flex flex-wrap gap-1>
                <el-tag v-for="act in row.act.split('|')" :key="act" size="small" type="info">
                  {{ act }}
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90" align="center" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="danger" plain @click="handleDeletePolicy(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 用户角色绑定 -->
      <el-tab-pane label="用户角色绑定" name="grouping">
        <div mb-3 flex justify-end>
          <el-button type="primary" size="small" :icon="Plus" @click="openGroupingDialog">
            新增绑定
          </el-button>
        </div>
        <el-table v-loading="groupingLoading" :data="filteredGroupings" stripe w-full>
          <el-table-column label="用户" min-width="200">
            <template #default="{ row }">
              <div>
                <div>{{ userLabel(row.user_id) }}</div>
                <div text-xs text-gray-4>{{ row.user_id }}</div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="角色" min-width="140">
            <template #default="{ row }">
              <el-tag size="small" type="warning">{{ roleLabel(row.role_key) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="域" min-width="120">
            <template #default="{ row }">
              <el-tag size="small" :type="row.dom === '*' ? 'danger' : 'primary'">{{ domLabel(row.dom) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90" align="center" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="danger" plain @click="handleDeleteGrouping(row)">移除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 新增策略对话框 -->
    <el-dialog v-model="policyDialogVisible" title="新增策略规则" width="90%" class="max-w-[480px]">
      <el-form :model="policyForm" :rules="policyRules" ref="policyFormRef" label-width="90px">
        <el-form-item label="主体(角色)" prop="sub">
          <el-select v-model="policyForm.sub" filterable allow-create placeholder="选择或输入角色" w-full>
            <el-option v-for="r in roleOptions" :key="r.role_key" :label="r.role_key" :value="r.role_key" />
          </el-select>
        </el-form-item>
        <el-form-item label="域" prop="dom">
          <el-select v-model="policyForm.dom" filterable allow-create placeholder="选择或输入域" w-full>
            <el-option v-for="opt in domOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="资源" prop="obj">
          <el-select v-model="policyForm.obj" filterable allow-create placeholder="选择或输入资源(*为全部)" w-full>
            <el-option v-for="o in resourceOptions" :key="o" :label="o" :value="o" />
          </el-select>
        </el-form-item>
        <el-form-item label="动作" prop="act">
          <el-select v-model="policyForm.act" filterable allow-create placeholder="选择或输入动作(多个用|分隔)" w-full>
            <el-option v-for="a in actionOptions" :key="a" :label="a" :value="a" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="policyDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleAddPolicy" :loading="submitting">确认</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 新增用户角色绑定对话框 -->
    <el-dialog v-model="groupingDialogVisible" title="新增用户角色绑定" width="90%" class="max-w-[480px]">
      <el-form :model="groupingForm" :rules="groupingRules" ref="groupingFormRef" label-width="90px">
        <el-form-item label="用户" prop="user_id">
          <el-select v-model="groupingForm.user_id" filterable placeholder="搜索并选择用户" w-full>
            <el-option v-for="u in userOptions" :key="u.id" :label="`${u.nickname || u.username} (${u.username})`"
              :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="角色" prop="role_key">
          <el-select v-model="groupingForm.role_key" filterable placeholder="选择角色" w-full>
            <el-option v-for="r in roleOptions" :key="r.role_key" :label="roleLabel(r.role_key)"
              :value="r.role_key" />
          </el-select>
        </el-form-item>
        <el-form-item label="域" prop="dom">
          <el-select v-model="groupingForm.dom" filterable allow-create placeholder="选择或输入域" w-full>
            <el-option v-for="opt in domOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="groupingDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleAddGrouping" :loading="submitting">确认</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Refresh, Plus } from '@element-plus/icons-vue'
import {
  getAllPolicies,
  getAllGroupingPolicies,
  addPolicy,
  removePolicy,
  addRoleForUser,
  removeRoleForUser,
  reloadPolicy,
  type PolicyRow,
  type GroupingPolicyRow,
} from '@/api/authorization/casbin'
import { listRoles } from '@/api/authorization/role'
import { listUsers } from '@/api/authorization/user'
import type { PaginationResponse } from '@/types/common'
import type { User } from '@/types/authorization/user'
import type { Role } from '@/types/authorization/role'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'

// 标签页状态
const activeTab = ref('policy')
const searchQuery = ref('')

// 域过滤
const domFilter = ref<string | undefined>(undefined)
// 域选项(main/rag模块 + 全局)
const domOptions = [
  { label: '全局(*)', value: '*' },
  { label: '主模块(main)', value: 'main' },
  { label: '知识库模块(rag)', value: 'rag' },
]
const domLabel = (dom: string) =>
  domOptions.find((o) => o.value === dom)?.label || dom

// 数据
const policies = ref<PolicyRow[]>([])
const groupings = ref<GroupingPolicyRow[]>([])
const policyLoading = ref(false)
const groupingLoading = ref(false)
const reloading = ref(false)
const submitting = ref(false)

// 选项数据
const roleOptions = ref<Role[]>([])
const userOptions = ref<User[]>([])
const userMap = ref<Map<string, User>>(new Map())

// 资源/动作提示选项(与后端预设保持一致)
const resourceOptions = ['*', 'project', 'doc', 'member', 'chat']
const actionOptions = ['*', 'read', 'create', 'update', 'delete', 'manage',
  'upload', 'invite', 'remove', 'write', 'read|create', 'read|write']

// 角色显示名(角色列表中无则原样展示)
const roleLabel = (key: string) => {
  const r = roleOptions.value.find((o) => o.role_key === key)
  return r?.name ? `${r.name}(${key})` : key
}

// 用户显示名
const userLabel = (userId: string) => {
  const u = userMap.value.get(userId)
  return u ? (u.nickname || u.username) : userId
}

// 客户端过滤
const filteredPolicies = computed(() => {
  const q = searchQuery.value
  if (!q) return policies.value
  return policies.value.filter(
    (p) => p.sub.includes(q) || p.obj.includes(q) || p.dom.includes(q)
  )
})
const filteredGroupings = computed(() => {
  const q = searchQuery.value
  if (!q) return groupings.value
  return groupings.value.filter(
    (g) => g.user_id.includes(q) || g.role_key.includes(q) || g.dom.includes(q)
  )
})

// 加载策略与绑定
const fetchAll = async () => {
  try {
    policyLoading.value = true
    groupingLoading.value = true
    const [pRes, gRes] = await Promise.all([
      getAllPolicies(domFilter.value),
      getAllGroupingPolicies(domFilter.value),
    ])
    policies.value = pRes.data
    groupings.value = gRes.data
  } catch (error) {
    console.error('获取策略失败:', error)
    ElMessage.error('获取策略数据失败')
  } finally {
    policyLoading.value = false
    groupingLoading.value = false
  }
}

// 加载角色与用户选项
const loadOptions = async () => {
  try {
    const [rRes, uRes] = await Promise.all([
      listRoles({ page: 1, size: 200 }),
      listUsers({ page: 1, size: 500 }),
    ])
    const roleData: PaginationResponse<Role> = rRes
    roleOptions.value = roleData.items || []
    userOptions.value = uRes.items
    userMap.value = new Map(uRes.items.map((u) => [u.id, u]))
  } catch (error) {
    console.error('加载选项失败:', error)
  }
}

// ---------------- 策略对话框 ----------------
const policyDialogVisible = ref(false)
const policyFormRef = ref<FormInstance>()
const policyForm = reactive({ sub: '', dom: 'main', obj: '*', act: 'read' })
const policyRules = {
  sub: [{ required: true, message: '请输入主体', trigger: 'blur' }],
  dom: [{ required: true, message: '请输入域', trigger: 'blur' }],
  obj: [{ required: true, message: '请输入资源', trigger: 'blur' }],
  act: [{ required: true, message: '请输入动作', trigger: 'blur' }],
}

const openPolicyDialog = () => {
  Object.assign(policyForm, { sub: '', dom: 'main', obj: '*', act: 'read' })
  policyDialogVisible.value = true
}

// 新增策略
const handleAddPolicy = async () => {
  if (!policyFormRef.value) return
  const valid = await policyFormRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    submitting.value = true
    await addPolicy({ ...policyForm })
    ElMessage.success('策略添加成功')
    policyDialogVisible.value = false
    fetchAll()
  } catch (error) {
    console.error('添加策略失败:', error)
    ElMessage.error('添加失败(策略可能已存在)')
  } finally {
    submitting.value = false
  }
}

// 删除策略
const handleDeletePolicy = async (row: PolicyRow) => {
  try {
    await ElMessageBox.confirm(
      `确定删除策略"${row.sub} / ${domLabel(row.dom)} / ${row.obj} / ${row.act}"吗？`,
      '警告',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    await removePolicy({ sub: row.sub, dom: row.dom, obj: row.obj, act: row.act })
    ElMessage.success('策略删除成功')
    fetchAll()
  } catch (error) {
    console.log('取消删除或删除失败:', error)
  }
}

// ---------------- 绑定对话框 ----------------
const groupingDialogVisible = ref(false)
const groupingFormRef = ref<FormInstance>()
const groupingForm = reactive({ user_id: '', role_key: '', dom: '*' })
const groupingRules = {
  user_id: [{ required: true, message: '请选择用户', trigger: 'change' }],
  role_key: [{ required: true, message: '请选择角色', trigger: 'change' }],
  dom: [{ required: true, message: '请输入域', trigger: 'blur' }],
}

const openGroupingDialog = () => {
  Object.assign(groupingForm, { user_id: '', role_key: '', dom: '*' })
  groupingDialogVisible.value = true
}

// 新增绑定
const handleAddGrouping = async () => {
  if (!groupingFormRef.value) return
  const valid = await groupingFormRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    submitting.value = true
    await addRoleForUser({
      user_id: groupingForm.user_id,
      role_key: groupingForm.role_key,
      dom: groupingForm.dom,
    })
    ElMessage.success('角色绑定成功')
    groupingDialogVisible.value = false
    fetchAll()
  } catch (error) {
    console.error('绑定失败:', error)
    ElMessage.error('绑定失败(用户可能已拥有该角色)')
  } finally {
    submitting.value = false
  }
}

// 移除绑定
const handleDeleteGrouping = async (row: GroupingPolicyRow) => {
  try {
    await ElMessageBox.confirm(
      `确定移除用户"${userLabel(row.user_id)}"在${domLabel(row.dom)}域的角色"${row.role_key}"吗？`,
      '警告',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    await removeRoleForUser({
      user_id: row.user_id,
      role_key: row.role_key,
      dom: row.dom,
    })
    ElMessage.success('角色绑定已移除')
    fetchAll()
  } catch (error) {
    console.log('取消移除或移除失败:', error)
  }
}

// 重载策略
const handleReload = async () => {
  try {
    reloading.value = true
    await reloadPolicy()
    ElMessage.success('策略已重新加载')
    fetchAll()
  } catch (error) {
    console.error('重载失败:', error)
    ElMessage.error('重载失败')
  } finally {
    reloading.value = false
  }
}

onMounted(() => {
  loadOptions()
  fetchAll()
})
</script>
