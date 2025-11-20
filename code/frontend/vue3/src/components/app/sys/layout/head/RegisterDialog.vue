<template>
  <el-dialog
    v-model="visible"
    :title="$t('sign_up')"
    :width="dialogWidth"
    :modal="true"
    :close-on-click-modal="true"
    :show-close="false"
    class="register-dialog"
    @close="handleClose"
  >
    <!-- 自定义头部以实现拖拽功能 -->
    <template #header="{ close, titleId, titleClass }">
      <div 
        class="dialog-header draggable-area" 
        @mousedown="startDrag"
        style="cursor: move; user-select: none;"
      >
        <span :id="titleId" :class="titleClass">{{ $t('sign_up') }}</span>
        <button class="el-dialog__headerbtn" @click="close" aria-label="Close">
          <el-icon><Close /></el-icon>
        </button>
      </div>
    </template>
    
    <div class="register-form">
      <el-form 
        ref="registerFormRef" 
        :model="registerForm" 
        :rules="registerRules as any"
        label-position="top"
        @submit.prevent="handleRegister"
      >
        <el-form-item :label="$t('username')" prop="username">
          <el-input 
            v-model="registerForm.username" 
            :placeholder="$t('username')" 
            autocomplete="username"
          />
        </el-form-item>
        
        <el-form-item :label="$t('email')" prop="email">
          <el-input 
            v-model="registerForm.email" 
            :placeholder="$t('email')" 
            autocomplete="email"
          />
        </el-form-item>
        
        <el-form-item label="密码" prop="password">
          <el-input 
            v-model="registerForm.password" 
            type="password" 
            placeholder="请输入密码" 
            autocomplete="new-password"
            show-password
          />
        </el-form-item>
        
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input 
            v-model="registerForm.confirmPassword" 
            type="password" 
            placeholder="请再次输入密码" 
            autocomplete="new-password"
            show-password
          />
        </el-form-item>
        
        <el-form-item>
          <el-button 
            type="primary" 
            class="w-full" 
            :loading="loading" 
            @click="handleRegister"
          >
            {{ $t('sign_up') }}
          </el-button>
        </el-form-item>
      </el-form>
      
      <div class="register-footer">
        <el-button type="info" link @click="handleBackToLogin">
          {{ $t('back_to_login') }}
        </el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { Close } from '@element-plus/icons-vue'
import type { FormInstance } from 'element-plus'

// 定义组件属性
const props = defineProps<{
  modelValue: boolean
}>()

// 定义事件发射
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'register-success', userInfo: { username: string }): void
  (e: 'back-to-login'): void
}>()

// 控制弹窗显示
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// 注册表单引用
const registerFormRef = ref<FormInstance>()

// 加载状态
const loading = ref(false)

// 注册表单数据
const registerForm = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: ''
})

// 表单验证规则
const registerRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度应在3-20个字符之间', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { 
      validator: (rule: unknown, value: string, callback: (error?: Error) => void) => {
        if (value !== registerForm.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

// 对话框宽度
const dialogWidth = ref('400px')

// 拖拽相关变量
let isDragging = false
let dragOffset = { x: 0, y: 0 }

// 开始拖拽
const startDrag = (e: MouseEvent) => {
  // 确保只在标题栏上按下鼠标左键才开始拖拽
  if (e.button !== 0) return
  
  isDragging = true
  const dialog = document.querySelector('.register-dialog .el-dialog') as HTMLElement
  if (!dialog) return
  
  // 获取对话框当前位置
  const rect = dialog.getBoundingClientRect()
  dragOffset = {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top
  }
  
  // 添加全局事件监听器
  document.addEventListener('mousemove', handleDrag)
  document.addEventListener('mouseup', stopDrag)
  
  // 防止文本选择
  e.preventDefault()
}

// 处理拖拽
const handleDrag = (e: MouseEvent) => {
  if (!isDragging) return
  
  const dialog = document.querySelector('.register-dialog .el-dialog') as HTMLElement
  if (!dialog) return
  
  // 计算新的位置
  const x = e.clientX - dragOffset.x
  const y = e.clientY - dragOffset.y
  
  // 设置位置
  dialog.style.position = 'fixed'
  dialog.style.left = `${x}px`
  dialog.style.top = `${y}px`
  dialog.style.transform = 'none' // 移除原有的transform
}

// 停止拖拽
const stopDrag = () => {
  isDragging = false
  document.removeEventListener('mousemove', handleDrag)
  document.removeEventListener('mouseup', stopDrag)
}

// 关闭弹窗
const handleClose = () => {
  visible.value = false
  // 重置表单
  registerFormRef.value?.resetFields()
}

// 处理注册
const handleRegister = async () => {
  if (!registerFormRef.value) return
  
  await registerFormRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        // 模拟注册请求
        await new Promise(resolve => setTimeout(resolve, 1000))
        // 发射注册成功事件
        emit('register-success', { username: registerForm.username })
        handleClose()
      } catch (error) {
        console.error('注册失败:', error)
      } finally {
        loading.value = false
      }
    }
  })
}

// 返回登录
const handleBackToLogin = () => {
  handleClose()
  emit('back-to-login')
}

// 组件卸载时清理事件监听器
onUnmounted(() => {
  document.removeEventListener('mousemove', handleDrag)
  document.removeEventListener('mouseup', stopDrag)
})
</script>

<style scoped>
.register-dialog :deep(.el-dialog) {
  border-radius: 8px;
  backdrop-filter: blur(10px);
  background: rgba(255, 255, 255, 0.8);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}

.register-dialog :deep(.el-dialog__header) {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
}

.register-dialog :deep(.el-dialog__body) {
  padding: 20px;
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.register-form {
  padding: 10px 0;
}

.register-footer {
  text-align: center;
  margin-top: 20px;
}

/* 暗色主题适配 */
.dark .register-dialog :deep(.el-dialog) {
  background: rgba(30, 30, 30, 0.8);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.dark .register-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
</style>