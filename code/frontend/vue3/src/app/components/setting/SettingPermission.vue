<template>
  <div max-w-[720px]>
    <h3 class="text-lg font-bold text-note mb-1">我的权限</h3>
    <p class="text-sm text-note-sub mb-5">当前账号在各模块域下绑定的角色与按钮级权限码(由管理员在角色管理中分配)。</p>

    <div v-loading="loading">
      <!-- 角色绑定(按域分组) -->
      <h4 class="text-sm font-medium text-note mb-2">角色绑定</h4>
      <div v-if="roleEntries.length" class="flex flex-col gap-2 mb-6">
        <div v-for="[dom, roles] in roleEntries" :key="dom"
          class="flex items-start gap-2 border border-note rounded px-3 py-2 flex-wrap">
          <el-tag size="small" :type="dom === '*' ? 'danger' : 'primary'" class="mt-0.5">{{ domLabel(dom) }}</el-tag>
          <div class="flex gap-1 flex-wrap">
            <el-tag v-for="r in roles" :key="r" size="small" type="warning">{{ r }}</el-tag>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无角色绑定" :image-size="60" />

      <!-- 权限码 -->
      <h4 class="text-sm font-medium text-note mb-2">权限码</h4>
      <template v-if="isSuperAdmin">
        <el-alert type="warning" :closable="false" title="全局管理员: 权限穿透一切" />
      </template>
      <template v-else-if="permissions.length">
        <div class="flex gap-1 flex-wrap">
          <el-tag v-for="p in permissions" :key="p" size="small" type="info">{{ p }}</el-tag>
        </div>
      </template>
      <el-empty v-else description="暂无按钮级权限码" :image-size="60" />
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

// 全局管理员权限码为 ["*"], 需要显示名映射的域走 label(仅常见域)
const domLabel = (dom: string) => (dom === '*' ? '全局(*)' : dom)

// 权限状态为空时拉取一次(登录后通常已缓存)
onMounted(async () => {
  if (roleEntries.value.length === 0) {
    try {
      loading.value = true
      await authStore.fetchPermissions()
    } finally {
      loading.value = false
    }
  }
})
</script>
