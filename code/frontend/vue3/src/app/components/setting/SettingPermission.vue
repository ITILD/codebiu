<template>
  <!-- 注意: max-w-[720px] 含方括号任意值, 必须写进 class 属性(attributify 陷阱, 见 App.vue) -->
  <div class="max-w-[720px]">
    <div class="flex items-center gap-2 mb-1">
      <h3 class="text-lg font-bold text-note">我的权限</h3>
      <el-tag size="small" type="info" effect="plain">只读</el-tag>
    </div>
    <p class="text-sm text-note-sub mb-5">
      {{ isSuperAdmin
        ? '您正以全局管理员身份浏览，全部模块的全部操作均已默认授信。'
        : '此处汇总您在各模块下被授予的功能与操作，如需调整请联系管理员。' }}
    </p>

    <div v-loading="loading">
      <!-- 模块权限(只读卡片: 模块 -> 功能 -> 动作) -->
      <div v-if="moduleCards.length" class="flex flex-col gap-4">
        <div v-for="card in moduleCards" :key="card.dom"
          class="border border-note rounded-lg p-3 bg-note-glass">
          <!-- 模块行 -->
          <div class="flex items-center gap-2 mb-2">
            <el-tag size="small" type="primary">{{ card.label }}</el-tag>
            <span class="text-xs text-note-sub font-mono">{{ card.dom }}</span>
          </div>
          <!-- 功能行: 功能名 + 已授权动作 -->
          <div class="flex flex-col gap-1.5">
            <div v-for="fn in card.functions" :key="fn.obj"
              class="flex items-center gap-2 flex-wrap text-sm">
              <span class="text-note min-w-[88px]">{{ fn.label }}</span>
              <el-tag v-for="act in fn.acts" :key="act.act" size="small" type="success" effect="plain">
                {{ act.label }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>
      <el-empty v-else-if="!isSuperAdmin" description="暂无模块权限, 请联系管理员分配" :image-size="60" />

      <!-- 角色绑定(只读) -->
      <template v-if="roleEntries.length">
        <h4 class="text-sm font-medium text-note mt-6 mb-2">角色绑定</h4>
        <div class="flex flex-col gap-2">
          <div v-for="[dom, roles] in roleEntries" :key="dom"
            class="flex items-start gap-2 border border-note rounded px-3 py-2 flex-wrap">
            <el-tag size="small" :type="dom === '*' ? 'danger' : 'primary'" class="mt-0.5">{{ domLabel(dom) }}</el-tag>
            <div class="flex gap-1 flex-wrap">
              <el-tag v-for="r in roles" :key="r" size="small" type="warning">{{ r }}</el-tag>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/common/stores/auth'

const authStore = useAuthStore()
const loading = ref(false)

const roleEntries = computed(() => Object.entries(authStore.permState.roles))
const permissions = computed(() => authStore.permState.permissions)
const isSuperAdmin = computed(() => permissions.value.includes('*'))

// ---------------- 权限树(与后端各模块 config/permissions.py 声明一致, 仅作展示) ----------------

interface ActItem { act: string; label: string }
interface FunctionDef { obj: string; label: string; acts: ActItem[] }
interface ModuleDef { dom: string; label: string; functions: FunctionDef[] }

/** 构造动作列表: 动作码与中文名成对传入, 如 a('read','查询','create','新增') */
function a(...pairs: string[]): ActItem[] {
  const items: ActItem[] = []
  for (let i = 0; i < pairs.length; i += 2) items.push({ act: pairs[i], label: pairs[i + 1] })
  return items
}

/** 全量权限树: 全局管理员直接展示; 普通用户按已授权码过滤并复用其中文名 */
const PERMISSION_TREE: ModuleDef[] = [
  {
    dom: 'sys',
    label: '系统管理',
    functions: [
      { obj: 'user', label: '用户管理', acts: a('read', '查询', 'create', '新增', 'update', '修改', 'delete', '删除') },
      { obj: 'role', label: '角色管理', acts: a('read', '查询', 'create', '新增', 'update', '修改', 'delete', '删除') },
      { obj: 'dept', label: '部门管理', acts: a('read', '查询', 'create', '新增', 'update', '修改', 'delete', '删除') },
      { obj: 'permission', label: '权限配置', acts: a('read', '查询', 'create', '新增', 'update', '修改', 'delete', '删除') },
      { obj: 'casbin', label: '策略规则', acts: a('read', '查询', 'create', '新增', 'update', '修改', 'delete', '删除') },
    ],
  },
  {
    dom: 'main',
    label: '基础资源',
    functions: [
      { obj: 'dict', label: '字典管理', acts: a('read', '查询', 'create', '新增', 'update', '修改', 'delete', '删除') },
      { obj: 'db', label: '数据库管理', acts: a('read', '查询') },
      { obj: 'file', label: '文件管理', acts: a('read', '浏览/下载', 'create', '上传/新建', 'update', '重命名/移动', 'delete', '删除', 'migrate', '存储迁移') },
      { obj: 'search', label: '网页搜索', acts: a('read', '使用') },
    ],
  },
  {
    dom: 'rag',
    label: '知识库',
    functions: [
      { obj: 'project', label: '项目管理', acts: a('read', '查询', 'create', '创建', 'update', '修改', 'delete', '删除') },
      { obj: 'doc', label: '文档管理', acts: a('read', '查看/下载', 'upload', '上传', 'update', '修改', 'delete', '删除') },
      { obj: 'member', label: '成员管理', acts: a('read', '查看', 'invite', '邀请', 'update', '变更角色', 'remove', '移除') },
      { obj: 'chat', label: '知识库问答', acts: a('read', '查看历史', 'write', '发起问答') },
    ],
  },
  {
    dom: 'agent',
    label: '智能体',
    functions: [
      { obj: 'chat', label: '智能体对话', acts: a('read', '查看历史', 'write', '发起对话') },
      { obj: 'manage', label: '智能体管理', acts: a('read', '查看', 'create', '创建', 'update', '修改', 'delete', '删除') },
    ],
  },
  {
    dom: 'geometry',
    label: '地理空间',
    functions: [
      { obj: 'feature', label: '要素管理', acts: a('read', '查询', 'create', '绘制', 'update', '修改', 'delete', '删除') },
    ],
  },
  {
    dom: 'site',
    label: '个人小站',
    functions: [
      { obj: 'blog', label: '博客', acts: a('read', '查询', 'create', '发布', 'update', '修改', 'delete', '删除') },
      { obj: 'memo', label: '备忘', acts: a('read', '查询', 'create', '新增', 'update', '修改', 'delete', '删除') },
      { obj: 'ledger', label: '记账', acts: a('read', '查询', 'create', '新增', 'update', '修改', 'delete', '删除') },
    ],
  },
  {
    dom: 'task',
    label: '任务队列',
    functions: [
      { obj: 'queue', label: '任务管理', acts: a('read', '查询', 'create', '创建', 'update', '操作', 'delete', '删除') },
    ],
  },
]

const domLabel = (dom: string) => PERMISSION_TREE.find((m) => m.dom === dom)?.label ?? dom

/** 已授权动作 -> 树中文名(优先功能内声明的名称, 兜底动作码通用映射) */
const ACT_FALLBACK: Record<string, string> = {
  read: '查看', create: '新增', update: '修改', delete: '删除',
  upload: '上传', write: '写入', invite: '邀请', remove: '移除', migrate: '存储迁移',
}
const resolveActs = (dom: string, obj: string, acts: string[]): ActItem[] => {
  const def = PERMISSION_TREE.find((m) => m.dom === dom)?.functions.find((f) => f.obj === obj)
  return acts.map((act) => ({
    act,
    label: def?.acts.find((x) => x.act === act)?.label ?? ACT_FALLBACK[act] ?? act,
  }))
}

interface FunctionCard { obj: string; label: string; acts: ActItem[] }
interface ModuleCard { dom: string; label: string; functions: FunctionCard[] }

/** 管理员: 展示全量权限树; 普通用户: 按 "模块:资源:动作" 权限码分组过滤 */
const moduleCards = computed<ModuleCard[]>(() => {
  if (isSuperAdmin.value) return PERMISSION_TREE

  // 权限码按 模块 -> 功能 分组收集动作
  const grouped = new Map<string, Map<string, Set<string>>>()
  for (const code of permissions.value) {
    const parts = code.split(':')
    if (parts.length !== 3) continue
    const [dom, obj, act] = parts
    if (!grouped.has(dom)) grouped.set(dom, new Map())
    const funcs = grouped.get(dom)!
    if (!funcs.has(obj)) funcs.set(obj, new Set())
    funcs.get(obj)!.add(act)
  }
  // 按 PERMISSION_TREE 声明顺序输出, 未收录模块排在最后
  const cards: ModuleCard[] = []
  const emit = (dom: string, label: string, funcs: Map<string, Set<string>>) => {
    cards.push({
      dom,
      label,
      functions: [...funcs.entries()].map(([obj, acts]) => ({
        obj,
        label: PERMISSION_TREE.find((m) => m.dom === dom)?.functions.find((f) => f.obj === obj)?.label ?? obj,
        acts: resolveActs(dom, obj, [...acts]),
      })),
    })
  }
  for (const mod of PERMISSION_TREE) {
    const funcs = grouped.get(mod.dom)
    if (funcs) {
      emit(mod.dom, mod.label, funcs)
      grouped.delete(mod.dom)
    }
  }
  for (const [dom, funcs] of grouped) emit(dom, dom, funcs)
  return cards
})

// 权限状态为空时拉取一次(登录后通常已缓存)
onMounted(async () => {
  if (permissions.value.length === 0 && Object.keys(roleEntries.value).length === 0) {
    try {
      loading.value = true
      await authStore.fetchPermissions()
    } finally {
      loading.value = false
    }
  }
})
</script>
