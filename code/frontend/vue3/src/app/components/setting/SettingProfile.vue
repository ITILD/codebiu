<template>
  <div max-w-[520px]>
    <h3 class="text-lg font-bold text-note mb-1">基本信息</h3>
    <p class="text-sm text-note-sub mb-5">维护你的昵称、联系方式与头像，登录后即可自助修改。</p>

    <!-- 头像预览 + 地址 -->
    <div class="flex items-center gap-4 mb-5">
      <el-avatar :size="64" :src="form.avatar || undefined" :icon="UserFilled" />
      <div class="flex-1">
        <el-input v-model="form.avatar" placeholder="头像图片地址(可选)" clearable>
          <template #prefix>URL</template>
        </el-input>
      </div>
    </div>

    <el-form :model="form" label-width="72px" label-position="left">
      <el-form-item label="用户名">
        <el-input :model-value="authState.user.username" disabled />
      </el-form-item>
      <el-form-item label="昵称">
        <el-input v-model="form.nickname" placeholder="展示用的昵称" maxlength="50" clearable />
      </el-form-item>
      <el-form-item label="邮箱">
        <el-input v-model="form.email" placeholder="name@example.com" maxlength="100" clearable />
      </el-form-item>
      <el-form-item label="电话">
        <el-input v-model="form.phone" placeholder="手机号" maxlength="20" clearable />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="handleSave">保存修改</el-button>
        <el-button @click="resetForm">重置</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { UserFilled } from '@element-plus/icons-vue'
import { updateMyProfile } from '@/modules/authorization/api/auth'
import { useAuthStore } from '@/common/stores/auth'
import { ElMessage } from 'element-plus'

const authStore = useAuthStore()
const authState = authStore.authState
const saving = ref(false)

// 表单初值取自登录会话中的用户信息
const buildForm = () => ({
  avatar: authState.user.avatar || '',
  nickname: authState.user.nickname || '',
  email: authState.user.email || '',
  phone: authState.user.phone || '',
})
const form = reactive(buildForm())

const resetForm = () => Object.assign(form, buildForm())

// 保存资料并同步到全局会话状态(持久化由 pinia persist 处理)
const handleSave = async () => {
  try {
    saving.value = true
    const updated = await updateMyProfile({
      nickname: form.nickname,
      email: form.email,
      phone: form.phone,
      avatar: form.avatar,
    })
    Object.assign(authState.user, updated)
    ElMessage.success('资料已更新')
  } catch (error) {
    console.error('更新资料失败:', error)
    ElMessage.error(error instanceof Error ? error.message : '更新资料失败')
  } finally {
    saving.value = false
  }
}
</script>
