<template>
  <el-dialog
    v-model="visible"
    :title="$t('sign_in')"
    :width="dialogWidth"
    :modal="true"
    :close-on-click-modal="true"
    draggable
    class="login-dialog"
    @close="handleClose"
  >
    <template #header="{ close, titleId, titleClass }">
      <div class="dialog-header">
        <span :id="titleId" :class="titleClass">{{ $t('sign_in') }}</span>
        <button class="el-dialog__headerbtn" @click="close" aria-label="Close">
          <el-icon><Close /></el-icon>
        </button>
      </div>
    </template>
    
    <div class="login-form">
      <el-form 
        ref="loginFormRef" 
        :model="loginForm" 
        :rules="loginRules" 
        label-position="top"
        @submit.prevent="handleLogin"
      >
        <el-form-item :label="$t('username')" prop="username">
          <el-input 
            v-model="loginForm.username" 
            :placeholder="$t('username')" 
            autocomplete="username"
          />
        </el-form-item>
        
        <el-form-item label="密码" prop="password">
          <el-input 
            v-model="loginForm.password" 
            type="password" 
            placeholder="请输入密码" 
            autocomplete="current-password"
            show-password
          />
        </el-form-item>
        
        <el-form-item>
          <el-checkbox v-model="loginForm.remember">记住我</el-checkbox>
        </el-form-item>
        
        <el-form-item>
          <el-button 
            type="primary" 
            class="w-full" 
            :loading="loading" 
            @click="handleLogin"
          >
            {{ $t('sign_in') }}
          </el-button>
        </el-form-item>
      </el-form>
      
      <div class="login-footer">
        <el-button type="info" link @click="handleRegister">
          {{ $t('sign_up') }}
        </el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { Close } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance } from 'element-plus'
import { loginUser } from '@/api/authorization/auth'
import type { AuthLoginRequest } from '@/types/authorization/auth'
// 用户信息和token设置
import { UserStore } from '@/stores/user'
const userStore = UserStore()
const userState = userStore.userState

// 定义组件属性
const props = defineProps<{
  modelValue: boolean
}>()

// 定义事件发射
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'login', userInfo: { username: string }): void
  (e: 'register'): void
}>()

// 控制弹窗显示
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// 登录表单引用
const loginFormRef = ref<FormInstance>()

// 加载状态
const loading = ref(false)

// 登录表单数据
const loginForm = reactive({
  username: '',
  password: '',
  remember: false
})

// 表单验证规则
const loginRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' }
  ]
}

// 对话框宽度
const dialogWidth = ref('400px')

// 关闭弹窗
const handleClose = () => {
  visible.value = false
  // 重置表单
  loginFormRef.value?.resetFields()
}

// 处理登录
const handleLogin = async () => {
  if (!loginFormRef.value) return
  
  await loginFormRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        // 准备登录数据
        const loginData: AuthLoginRequest = {
          username: loginForm.username,
          password: loginForm.password
        }
        
        // 调用登录API
        const response = await loginUser(loginData)
        
        // 发射登录事件
        emit('login', { username: loginForm.username })
        handleClose()
      } catch (error: any) {
        debugger
        console.error('登录失败:', error)
        // 添加错误提示
        ElMessage.error(error.message || '登录失败，请检查用户名和密码')
      } finally {
        loading.value = false
      }
    }
  })
}

// 处理注册
const handleRegister = () => {
  handleClose()
  emit('register')
}


</script>

<style scoped>
.login-dialog :deep(.el-dialog) {
  border-radius: 8px;
  backdrop-filter: blur(10px);
  background: rgba(255, 255, 255, 0.8);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}

.login-dialog :deep(.el-dialog__header) {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
}

.login-dialog :deep(.el-dialog__body) {
  padding: 20px;
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.login-form {
  padding: 10px 0;
}

.login-footer {
  text-align: center;
  margin-top: 20px;
}

/* 暗色主题适配 */
.dark .login-dialog :deep(.el-dialog) {
  background: rgba(30, 30, 30, 0.8);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.dark .login-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
</style>