<template>
  <div w-full>
    <!-- 统计卡: 角色/模块域/策略/绑定 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
      <div v-for="s in statCards" :key="s.label" class="page-card">
        <div class="text-xs text-note-sub">{{ s.label }}</div>
        <div class="text-2xl font-bold text-note mt-1">{{ s.value }}</div>
      </div>
    </div>

    <!-- 角色 × 模块域 权限矩阵 -->
    <div class="bg-note-card rounded-lg shadow-note p-3 overflow-x-auto">
      <div class="text-sm text-note-sub mb-2">
        点击单元格查看/编辑该角色在此模块域的策略明细；"全部"表示通配策略(资源=*)，"—"表示暂无策略
      </div>
      <table v-loading="loading" class="w-full min-w-[680px] border-collapse">
        <thead>
          <tr>
            <th class="text-left p-2 text-note-sub text-sm font-normal min-w-[160px]">角色 \ 模块域</th>
            <th v-for="d in doms" :key="d" class="p-2 text-note-sub text-sm font-normal whitespace-nowrap">
              {{ domLabel(d) }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in roleKeys" :key="r" class="border-t border-note">
            <td class="p-2">
              <el-tag size="small" type="warning">{{ roleLabel(r) }}</el-tag>
            </td>
            <td v-for="d in doms" :key="d" class="p-1 text-center">
              <!-- 有策略: 全部/计数徽标 -->
              <el-tooltip v-if="cellPolicies(r, d).length" :content="`点击查看 ${roleLabel(r)} 在 ${domLabel(d)} 的策略`"
                placement="top">
                <button class="w-full cursor-pointer rounded px-2 py-1 transition-opacity hover:opacity-80"
                  @click="openDetail(r, d)">
                  <el-tag v-if="cellWildcard(r, d)" size="small" type="danger" effect="dark">全部</el-tag>
                  <el-tag v-else size="small" type="success">{{ cellPolicies(r, d).length }} 项</el-tag>
                </button>
              </el-tooltip>
              <!-- 无策略: 快捷添加入口 -->
              <el-tooltip v-else :content="`为 ${roleLabel(r)} 添加 ${domLabel(d)} 策略`" placement="top">
                <button class="w-full cursor-pointer rounded px-2 py-1.5 text-note-sub hover:bg-note-glass"
                  @click="openDetail(r, d)">—</button>
              </el-tooltip>
            </td>
          </tr>
        </tbody>
      </table>
      <el-empty v-if="!loading && roleKeys.length === 0" description="暂无策略数据" />
    </div>

    <!-- 明细抽屉: 某角色在某域的策略明细与增删 -->
    <el-drawer v-model="drawerVisible" :title="drawerTitle" size="440px" class="max-w-[92vw]">
      <div v-loading="drawerLoading">
        <!-- 通配策略警示 -->
        <el-alert v-if="cellWildcard(currentRole, currentDom)" type="warning" :closable="false" class="mb-3"
          title="该角色在此域拥有通配策略(资源=*), 拥有全部资源权限, 删除前请确认影响范围" />

        <!-- 策略明细列表 -->
        <div v-for="(p, i) in drawerPolicies" :key="i"
          class="flex items-center justify-between gap-2 border border-note rounded px-3 py-2 mb-2">
          <div class="flex items-center gap-1 flex-wrap">
            <el-tag size="small">{{ p.obj }}</el-tag>
            <span class="text-note-sub text-xs">/</span>
            <el-tag v-for="a in p.act.split('|')" :key="a" size="small" type="info">{{ a }}</el-tag>
          </div>
          <el-button size="small" type="danger" plain @click="handleRemovePolicy(p)">删除</el-button>
        </div>
        <el-empty v-if="!drawerPolicies.length" description="暂无策略, 可在下方添加" :image-size="60" />

        <el-divider content-position="left">添加策略</el-divider>
        <!-- 快捷添加: 资源/动作来自模块声明树, 支持手动输入 -->
        <el-form label-width="56px">
          <el-form-item label="资源">
            <el-select v-model="addForm.obj" filterable allow-create placeholder="选择或输入资源" w-full>
              <el-option v-for="o in drawerResourceOptions" :key="o" :label="o" :value="o" />
            </el-select>
          </el-form-item>
          <el-form-item label="动作">
            <el-select v-model="addForm.acts" multiple filterable allow-create placeholder="选择或输入动作(可多选)" w-full>
              <el-option v-for="a in drawerActionOptions" :key="a" :label="a" :value="a" />
            </el-select>
          </el-form-item>
          <el-button type="primary" w-full :loading="submitting" @click="handleAddPolicy">添加策略</el-button>
        </el-form>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import {
  getAllPolicies,
  getAllGroupingPolicies,
  addPolicy,
  removePolicy,
  getModuleTree,
  type PolicyRow,
  type ModulePermNode,
} from '../api/casbin'
import { listRoles } from '../api/role'
import type { PaginationResponse } from '@/common/types/common'
import type { Role } from '../types/role'
import { ElMessage, ElMessageBox } from 'element-plus'

// ---------------- 基础数据 ----------------
const loading = ref(false)
const submitting = ref(false)
const policies = ref<PolicyRow[]>([])
const bindCount = ref(0)
const roleOptions = ref<Role[]>([])
const moduleTree = ref<ModulePermNode[]>([])

// 全部角色键(角色表 ∪ 策略主体), '*' 通配域排最前
const roleKeys = computed(() => {
  const set = new Set<string>()
  roleOptions.value.forEach((r) => set.add(r.role_key))
  policies.value.forEach((p) => set.add(p.sub))
  return [...set].sort((a, b) => a.localeCompare(b))
})

// 全部模块域(策略域 ∪ 模块声明), '*' 排最前
const doms = computed(() => {
  const set = new Set<string>()
  policies.value.forEach((p) => set.add(p.dom))
  moduleTree.value.forEach((m) => set.add(m.code))
  return [...set].sort((a, b) => (a === '*' ? -1 : b === '*' ? 1 : a.localeCompare(b)))
})

// 矩阵映射: 角色 -> 域 -> 策略列表
const matrixMap = computed(() => {
  const map: Record<string, Record<string, PolicyRow[]>> = {}
  for (const p of policies.value) {
    if (!map[p.sub]) map[p.sub] = {}
    if (!map[p.sub][p.dom]) map[p.sub][p.dom] = []
    map[p.sub][p.dom].push(p)
  }
  return map
})

const cellPolicies = (role: string, dom: string): PolicyRow[] => matrixMap.value[role]?.[dom] || []

// 通配单元格: 存在 obj='*' 的策略
const cellWildcard = (role: string, dom: string) => cellPolicies(role, dom).some((p) => p.obj === '*')

// 统计卡
const statCards = computed(() => [
  { label: '角色数', value: roleKeys.value.length },
  { label: '模块域数', value: doms.value.filter((d) => d !== '*').length },
  { label: '策略数', value: policies.value.length },
  { label: '用户绑定数', value: bindCount.value },
])

// ---------------- 显示名辅助 ----------------
const roleLabel = (key: string) => {
  const r = roleOptions.value.find((o) => o.role_key === key)
  return r?.name ? `${r.name}(${key})` : key
}
const domLabel = (dom: string) => {
  if (dom === '*') return '全局(*)'
  const m = moduleTree.value.find((x) => x.code === dom)
  return m ? `${m.name}(${dom})` : dom
}

// ---------------- 模块声明树 → 资源/动作候选 ----------------
// 收集某域下全部按钮级权限码, 解析为 (资源, 动作) 组合
const domResourceActions = computed(() => {
  const map: Record<string, { objs: Set<string>; objActs: Record<string, Set<string>> }> = {}
  const walk = (nodes: ModulePermNode[]) => {
    for (const n of nodes) {
      const parts = n.code.split(':')
      if (n.menu_type === 'F' && parts.length === 3) {
        const [, obj, act] = parts
        if (!map[parts[0]]) map[parts[0]] = { objs: new Set(), objActs: {} }
        map[parts[0]].objs.add(obj)
        if (!map[parts[0]].objActs[obj]) map[parts[0]].objActs[obj] = new Set()
        map[parts[0]].objActs[obj].add(act)
      }
      if (n.children?.length) walk(n.children)
    }
  }
  walk(moduleTree.value)
  return map
})

// ---------------- 明细抽屉 ----------------
const drawerVisible = ref(false)
const drawerLoading = ref(false)
const currentRole = ref('')
const currentDom = ref('')
const addForm = reactive({ obj: '', acts: [] as string[] })

const drawerTitle = computed(() => `${roleLabel(currentRole.value)} @ ${domLabel(currentDom.value)}`)

// 当前角色+域的策略(打开抽屉时从最新数据实时取)
const drawerPolicies = computed(() => cellPolicies(currentRole.value, currentDom.value))

// 抽屉内资源/动作候选(当前域的声明 + 通配 + 常用动作)
const drawerResourceOptions = computed(() => {
  const decl = domResourceActions.value[currentDom.value]
  const objs = decl ? [...decl.objs] : []
  return ['*', ...objs.filter((o) => o !== '*')]
})
const drawerActionOptions = computed(() => {
  const decl = domResourceActions.value[currentDom.value]
  const acts = new Set<string>()
  if (decl) Object.values(decl.objActs).forEach((s) => s.forEach((a) => acts.add(a)))
  // 常用动作兜底
  ;['read', 'create', 'update', 'delete'].forEach((a) => acts.add(a))
  return [...acts]
})

const openDetail = (role: string, dom: string) => {
  currentRole.value = role
  currentDom.value = dom
  Object.assign(addForm, { obj: '', acts: [] })
  drawerVisible.value = true
}

// 添加策略(动作多选拼接为 a|b)
const handleAddPolicy = async () => {
  if (!addForm.obj || addForm.acts.length === 0) {
    ElMessage.warning('请选择资源与至少一个动作')
    return
  }
  try {
    submitting.value = true
    await addPolicy({ sub: currentRole.value, dom: currentDom.value, obj: addForm.obj, act: addForm.acts.join('|') })
    ElMessage.success('策略添加成功')
    await refresh()
  } catch (error) {
    console.error('添加策略失败:', error)
    ElMessage.error('添加失败(策略可能已存在)')
  } finally {
    submitting.value = false
  }
}

// 删除策略(通配策略二次确认)
const handleRemovePolicy = async (row: PolicyRow) => {
  try {
    const tip = row.obj === '*' ? '这是通配策略, 删除后该角色将失去此域全部资源权限' : ''
    await ElMessageBox.confirm(
      `确定删除策略 "${row.sub} / ${row.dom} / ${row.obj} / ${row.act}" 吗？${tip}`,
      '警告',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    await removePolicy({ sub: row.sub, dom: row.dom, obj: row.obj, act: row.act })
    ElMessage.success('策略删除成功')
    await refresh()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    console.error('删除策略失败:', error)
  }
}

// ---------------- 数据加载 ----------------
const refresh = async () => {
  try {
    drawerLoading.value = true
    loading.value = true
    const [pRes, gRes, rRes, tRes] = await Promise.all([
      getAllPolicies(),
      getAllGroupingPolicies(),
      listRoles({ page: 1, size: 200 }),
      getModuleTree(),
    ])
    policies.value = pRes.data
    bindCount.value = gRes.data.length
    roleOptions.value = (rRes as PaginationResponse<Role>).items || []
    moduleTree.value = tRes.data
  } catch (error) {
    console.error('获取策略数据失败:', error)
    ElMessage.error('获取策略数据失败')
  } finally {
    loading.value = false
    drawerLoading.value = false
  }
}

onMounted(refresh)
</script>
